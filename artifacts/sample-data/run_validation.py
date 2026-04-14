import csv, re, sys

REQUIRED = ['PersonId', 'EffectiveDate', 'ManagerId', 'Organization']
RESERVED = {
    'FunctionType': 'String', 'LevelDesignation': 'String', 'HireDate': 'DateTime',
    'HourlyRate': 'Double', 'Layer': 'Integer', 'SupervisorIndicator': 'String',
    'WeeklyBadgeOnsiteDays': 'Double', 'Location': 'String', 'CountryOrRegion': 'String'
}
FORBIDDEN = ['TimeZone','Domain','PopulationType','StartDate','EndDate','ObjectId',
             'IsActive','MetricDate','StandardTimeZone','WorkdayStart','WorkDayEnd',
             'WeekendDays','InferredTeamSize']
SENTINEL = ['#N/A','N/A','NULL','null','none','n/a','NA']

def validate(fp, label):
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {label}")
    print(f"  File: {fp}")
    print(sep)
    
    with open(fp) as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        rows = list(reader)
    
    pids = set(r.get('PersonId','') for r in rows if r.get('PersonId','').strip())
    mids = set(r.get('ManagerId','') for r in rows if r.get('ManagerId','').strip())
    orphans = mids - pids
    all_pids = [r.get('PersonId','') for r in rows]
    dup_count = len(all_pids) - len(set(all_pids))
    forbidden_found = [h for h in headers if h in FORBIDDEN]
    empty_cols = [h for h in headers if all(not r[h].strip() for r in rows)]
    
    # 1. Summary
    print(f"\n## 1. FILE SUMMARY")
    print(f"  Rows: {len(rows)}, Columns: {len(headers)}")
    print(f"  Unique PersonIds: {len(pids)}, Duplicates: {dup_count}")
    print(f"  Forbidden columns: {forbidden_found if forbidden_found else 'None'}")
    print(f"  Total attributes: {len(headers)}/105 max")
    
    # 2. Required
    print(f"\n## 2. REQUIRED ATTRIBUTES")
    for attr in REQUIRED:
        if attr in headers:
            filled = sum(1 for r in rows if r[attr].strip())
            pct = filled / len(rows) * 100
            if attr == 'ManagerId':
                blanks = sum(1 for r in rows if not r[attr].strip())
                status = "PASS" if blanks <= 1 else f"WARNING ({blanks} blank)"
            elif pct == 100:
                status = "PASS"
            elif pct == 0:
                status = "CRITICAL FAIL (0%)"
            else:
                status = f"FAIL ({pct:.0f}%)"
            print(f"  {attr}: {filled}/{len(rows)} ({pct:.0f}%) -> {status}")
        else:
            print(f"  {attr}: MISSING -> CRITICAL FAIL")
    
    if 'PersonId' in headers and 'ManagerId' in headers:
        print(f"  Hierarchy: {len(orphans)}/{len(mids)} managers NOT in PersonId list")
        if orphans and len(orphans) <= 5:
            print(f"    Orphaned: {list(orphans)}")
        elif orphans:
            print(f"    Orphaned (first 5): {list(orphans)[:5]}...")
    
    # 3. Reserved
    print(f"\n## 3. RESERVED ATTRIBUTES")
    for attr, dtype in RESERVED.items():
        if attr in headers:
            vals = [r[attr].strip() for r in rows if r[attr].strip()]
            uniq = set(vals)
            filled_pct = len(vals) / len(rows) * 100
            issues = []
            
            if dtype == 'Integer':
                non_int = [v for v in uniq if not v.lstrip('-').isdigit()]
                if non_int:
                    issues.append(f"NON-INTEGER values: {list(non_int)[:5]}")
            elif dtype == 'Double':
                non_dbl = [v for v in uniq if not re.match(r'^-?\d+\.?\d*$', v)]
                if non_dbl:
                    issues.append(f"INVALID format: {list(non_dbl)[:5]}")
            elif dtype == 'DateTime':
                sents = [v for v in uniq if v in SENTINEL or v.startswith('0/')]
                placeholders = [v for v in uniq if '1900' in v or '1970' in v or '9999' in v]
                if sents:
                    issues.append(f"SENTINEL/INVALID: {sents}")
                if placeholders:
                    issues.append(f"PLACEHOLDER dates: {list(placeholders)[:3]}")
            
            status = "PASS" if not issues else "FAIL"
            print(f"  {attr}: {len(vals)}/{len(rows)} filled ({filled_pct:.0f}%), {len(uniq)} unique -> {status}")
            for iss in issues:
                print(f"    ! {iss}")
        else:
            print(f"  {attr}: not present")
    
    # 4. Data Quality
    print(f"\n## 4. DATA QUALITY ISSUES")
    issue_count = 0
    # Sentinels
    for col in headers:
        for i, r in enumerate(rows):
            v = r[col].strip()
            if v in SENTINEL:
                issue_count += 1
                print(f"  [{issue_count}] SENTINEL row {i+2}: {col} = '{v}'")
    # Empty columns
    if empty_cols:
        issue_count += 1
        print(f"  [{issue_count}] 100% EMPTY columns ({len(empty_cols)}): {empty_cols}")
    # Parenthetical IDs
    paren_cols = [h for h in headers if any(re.search(r'\(\d{3,}\)', r[h]) for r in rows)]
    if paren_cols:
        issue_count += 1
        print(f"  [{issue_count}] PARENTHETICAL IDs in: {paren_cols}")
    # Date format
    for dc in [h for h in headers if 'date' in h.lower()]:
        vals = [r[dc].strip() for r in rows if r[dc].strip() and r[dc].strip() not in SENTINEL]
        if vals:
            has_slash = any('/' in v for v in vals)
            has_dash = any(v[0].isdigit() and '-' in v for v in vals)
            if has_slash and has_dash:
                issue_count += 1
                print(f"  [{issue_count}] MIXED date separators in {dc}")
            elif has_dash:
                issue_count += 1
                print(f"  [{issue_count}] {dc} uses YYYY-MM-DD format (sample: {vals[0]})")
    # Duplicates
    if dup_count > 0:
        from collections import Counter
        dupes = [k for k, v in Counter(all_pids).items() if v > 1]
        issue_count += 1
        print(f"  [{issue_count}] DUPLICATE PersonIds: {dupes}")
    # Forbidden
    if forbidden_found:
        issue_count += 1
        print(f"  [{issue_count}] FORBIDDEN system columns: {forbidden_found}")
    
    if issue_count == 0:
        print(f"  No issues found.")
    
    # 8. Dashboard Impact
    print(f"\n## 8. DASHBOARD IMPACT ASSESSMENT")
    org_ok = 'Organization' in headers and any(r['Organization'].strip() for r in rows)
    func_ok = 'FunctionType' in headers and any(r['FunctionType'].strip() for r in rows)
    hier_ok = len(orphans) < len(mids) * 0.5 if mids else False
    
    print(f"  Organization filter:  {'WILL WORK' if org_ok else 'WILL NOT APPEAR'}")
    print(f"  Job Function filter:  {'WILL WORK' if func_ok else 'WILL NOT APPEAR (no Entra fallback)'}")
    print(f"  Scope/Group view:     {'WILL WORK' if hier_ok else 'BROKEN - only Your company visible'}")
    
    if org_ok:
        org_vals = set(r['Organization'].strip() for r in rows if r['Organization'].strip())
        print(f"    Org values ({len(org_vals)}): {list(org_vals)[:6]}{'...' if len(org_vals)>6 else ''}")
    if func_ok:
        func_vals = set(r['FunctionType'].strip() for r in rows if r['FunctionType'].strip())
        print(f"    Function values ({len(func_vals)}): {list(func_vals)[:6]}")
    
    if not org_ok:
        print(f"    -> Adoption+Impact pages: Leaders cannot compare by business unit")
    if not func_ok:
        print(f"    -> Adoption+Impact pages: Cannot compare by job role")
    if not hier_ok:
        print(f"    -> All pages: No group drilldown. Manager/team views empty.")
    
    # Grade
    critical = 0
    if not org_ok and 'Organization' in headers: critical += 1
    if 'PersonId' not in headers: critical += 1
    if 'ManagerId' not in headers: critical += 1
    if 'EffectiveDate' not in headers: critical += 1
    if hier_ok is False and mids: critical += 1
    if forbidden_found: critical += 1
    if dup_count > 0: critical += 1
    
    if critical == 0 and issue_count <= 2:
        grade = "A — Ready to upload"
    elif critical == 0:
        grade = "B — Minor fixes recommended"
    elif critical <= 2:
        grade = "C — Significant fixes needed"
    else:
        grade = "D — Major rework required"
    
    print(f"\n  OVERALL GRADE: {grade}")
    print(f"  Critical issues: {critical}, Total issues: {issue_count}")

# Run all three
datasets = [
    ('artifacts/sample-data/dataset1_good.csv', 'DATASET 1: GOOD DATA'),
    ('artifacts/sample-data/dataset2_partial.csv', 'DATASET 2: PARTIALLY GOOD'),
    ('artifacts/sample-data/dataset3_bad.csv', 'DATASET 3: MAJOR IMPROVEMENTS NEEDED'),
]
for fp, label in datasets:
    validate(fp, label)

print(f"\n{'='*70}")
print("  ALL SIMULATIONS COMPLETE")
print(f"{'='*70}")
