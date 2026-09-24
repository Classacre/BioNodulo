# CWL File Input

Use **CWL File Input** when an unchanged CWL descriptor declares a `format` on a `File` input. The node copies the selected primary file and any explicitly listed secondary files into the current run, then emits a standard CWL `File` object on a normal `FILE` socket.

`format_uri` must be a credential-free absolute URI such as `http://edamontology.org/format_1929`. It is an explicit user declaration. BioNodulo does not infer it from a filename, inspect the bytes to prove the scientific format, or copy a format required by the downstream consumer. The reference CWL engine checks whether the declared URI is compatible with the descriptor.

`secondary_files` accepts a JSON array. Each entry must have `"class": "File"` and exactly one `location` or `path`. Optional `basename` and `format` fields are retained. Nested secondary files are outside this primitive's bounded profile. All supplied files are copied; their original paths are not passed to the tool.

The existing **Input File** node remains path-only and does not declare CWL metadata.
