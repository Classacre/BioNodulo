#!/usr/bin/env python3
"""Replace synthesized html_report nodes in templates with direct render nodes.

For each html_report:
  - every feeder into its `tables` input  -> a table_preview node
  - every feeder into its `images` input  -> an image_preview node
  - drop the html_report node and the html_preview that previewed it
html_previews fed by real tool HTML (multiqc, quast, qc_dashboard, ...) are kept.
Positions for the new render nodes are placed to the right of the old report;
the column de-overlap pass (templateLayout) is run afterwards to tidy.
"""
import json
import glob
import os
import sys

def feeders(edges, node, port=None):
    out = []
    for e in edges:
        t = e.get('to', {}).get('node')
        ti = e.get('to', {}).get('input')
        if t == node and (port is None or ti == port):
            out.append((e.get('from', {}).get('node'), e.get('from', {}).get('output')))
    return out

def main(write):
    total_reports = 0
    total_new = 0
    for path in sorted(glob.glob('templates/*.json')):
        raw = json.load(open(path))
        wf = raw.get('workflow', raw)
        nodes = wf['nodes']
        edges = wf['edges']
        reports = [n for n in nodes if n['type'] == 'html_report']
        if not reports:
            continue

        remove_ids = set()
        new_nodes = []
        new_edges = []

        for rep in reports:
            rid = rep['id']
            remove_ids.add(rid)
            pos = rep.get('position', [0, 0])
            base_x = pos[0] + 360
            y = pos[1]
            # Table feeders -> table_preview ; image feeders -> image_preview.
            specs = [('tables', 'table_preview', 'View Table'),
                     ('images', 'image_preview', 'View Figure')]
            idx = 0
            for port, render_type, title in specs:
                seen = set()
                for src, src_out in feeders(edges, rid, port):
                    if src is None or (src, src_out) in seen:
                        continue
                    seen.add((src, src_out))
                    short = src.replace('_001', '')
                    nid = f"render_{short}_{port[:3]}_{idx}"
                    new_nodes.append({
                        'id': nid,
                        'type': render_type,
                        'position': [base_x, y + idx * 220],
                        'params': {},
                        'ui': {'title': f"{title}: {short}"},
                    })
                    new_edges.append({
                        'from': {'node': src, 'output': src_out},
                        'to': {'node': nid, 'input': 'file'},
                    })
                    idx += 1

            # Remove the html_preview(s) that previewed THIS report.
            for n in nodes:
                if n['type'] != 'html_preview':
                    continue
                if any(s == rid for s, _ in feeders(edges, n['id'])):
                    remove_ids.add(n['id'])

        # Drop removed nodes + any edge touching them.
        wf['nodes'] = [n for n in nodes if n['id'] not in remove_ids] + new_nodes
        wf['edges'] = [
            e for e in edges
            if e.get('from', {}).get('node') not in remove_ids
            and e.get('to', {}).get('node') not in remove_ids
        ] + new_edges

        total_reports += len(reports)
        total_new += len(new_nodes)
        print(f"{os.path.basename(path):46s} -reports={len(reports)} +render={len(new_nodes)} removed={len(remove_ids)}")

        if write:
            json.dump(raw, open(path, 'w'), indent=2)
            open(path, 'a').write('\n')

    print(f"\nremoved {total_reports} html_report nodes, added {total_new} render nodes"
          f"{' (written)' if write else ' (dry run)'}")

if __name__ == '__main__':
    main('--write' in sys.argv)
