"""V5 descriptive metrics stratified by the independently assigned policy wording."""
from collections import defaultdict
from shared import analysis as v5

def summarize(episodes):
    groups = defaultdict(list)
    for row in episodes:
        groups[row['instruction_strength']].append(row)
    cells = []
    assumptions = []
    for strength, rows in sorted(groups.items()):
        summary = v5.summarize(rows)
        assumptions = summary['assumptions']
        cells.extend(dict(cell, instruction_strength=strength) for cell in summary['cells'])
    return {'schema_version': 2, 'total_attempts': len(episodes), 'cells': cells,
            'assumptions': assumptions + [
                'Instruction strength is wording assigned by the experiment, not a validated psychological scale.',
                'Controls are shared across strength comparisons; matched seeds and repeated decisions are not independent replicates.',
                'No-tool controls assess computational workload separately from instruction-strength effects.']}
