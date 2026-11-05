"""Regression: a partial source cannot establish that an unseen merchant is missing."""
import copy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import import_verified_snapshots as imp

prior = [
    dict(name='Seen',wi='Seen',wiUrl='https://www.widilo.fr/code-promo/seen',wiRate='5%',wiDate='2026-11-04'),
    dict(name='Unseen',wi='Unseen',wiUrl='https://www.widilo.fr/code-promo/unseen',wiRate='8%',wiDate='2026-11-04'),
    dict(name='Historical',wi='Historical',wiUrl='https://www.widilo.fr/code-promo/historical',wiDate='2026-11-02',wiMissingSince='2026-11-03'),
]
source = dict(name='Seen',wi='Seen',wiUrl=prior[0]['wiUrl'],wiRate='',wiDate='2026-11-05')
rows = copy.deepcopy(prior)
result = imp.apply(rows,[source],'wi','2026-11-05',{},complete=False)
assert rows[1:] == prior[1:], 'unseen observations and historical flags must remain unchanged'
assert result['missing'] == []
assert rows[0]['wiRate'] == '5%' and rows[0]['wiRateDate'] == '2026-11-04'
assert rows[0]['wiDate'] == '2026-11-05'
full = copy.deepcopy(prior)
assert len(imp.apply(full,[source],'wi','2026-11-05',{})['missing']) == 2
print('PASS: partial snapshot preserves unseen merchants, historical flags and last known rates; complete snapshots still detect absences.')
