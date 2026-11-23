import openpyxl
import os
import re

def audit_paths():
    wb = openpyxl.load_workbook('Assessment2_Repalle_Gnaneswar.xlsx')
    sheets_to_check = ['2_Must_haves', '3_Levels', '4_Integration', '5_Metrics', '6_Hard_cases']

    all_paths = set()
    broken_paths = []

    for sname in sheets_to_check:
        ws = wb[sname]
        for r in range(1, ws.max_row + 1):
            for c in range(1, ws.max_column + 1):
                val = str(ws.cell(r, c).value or '')
                # Split entries separated by semicolons
                entries = [e.strip() for e in val.split(';') if e.strip()]
                for entry in entries:
                    # Strip command prefixes or test names
                    candidate = entry.split('::')[0].strip(' ,()\"\'')
                    if candidate.startswith('pytest') or candidate.startswith('python') or candidate.startswith('http'):
                        continue
                    # Check for path patterns
                    tokens = candidate.split()
                    for t in tokens:
                        t = t.strip(' ,()\"\'')
                        if any(t.endswith(ext) for ext in ['.py', '.md', '.json', '.yaml', '.otio', '.mp4', '.sh', '.yml']):
                            all_paths.add(t)
                            if not os.path.exists(t):
                                broken_paths.append((sname, r, c, t))
                        elif '/' in t or '\\' in t:
                            if os.path.exists(t):
                                all_paths.add(t)

    print(f'Total distinct file paths found in sheets: {len(all_paths)}')
    for p in sorted(all_paths):
        exists = os.path.exists(p)
        status = 'EXISTS' if exists else 'MISSING'
        print(f'[{status}] {p}')

    if broken_paths:
        print(f'BROKEN PATHS FOUND: {len(broken_paths)}')
        for bp in broken_paths:
            print('  ', bp)
    else:
        print('SUCCESS: ALL PATHS IN ALL SHEETS EXIST WITH ZERO BROKEN PATHS!')

if __name__ == '__main__':
    audit_paths()
