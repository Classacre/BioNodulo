cwlVersion: v1.0
class: CommandLineTool
hints:
- class: DockerRequirement
  dockerPull: biowardrobe2/ucscuserapps:v358
baseCommand: sleep
inputs:
  seconds:
    type: int
    inputBinding:
      position: 1
outputs:
  unused:
    type: File?
    outputBinding:
      glob: never-created.txt
