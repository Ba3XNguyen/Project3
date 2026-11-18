"""Exercise all pages, datasets and time filtering with real artifacts."""
import json
from pathlib import Path
from streamlit.testing.v1 import AppTest

checks=[]
for dataset in ('Skill Builder','Non-Skill Builder'):
    at=AppTest.from_file(str(Path(__file__).with_name('app.py')),default_timeout=90).run()
    at.sidebar.selectbox[0].select(dataset).run()
    assert not at.exception, at.exception
    checks.append(f'{dataset}: performance')
    for page in ('Student Replay','Skill Analysis'):
        at.sidebar.radio[0].set_value(page).run()
        assert not at.exception, at.exception
        slider=at.select_slider[0]
        slider.set_value(int(slider.options[min(2,len(slider.options)-1)])).run()
        assert not at.exception, at.exception
        pos=int(at.select_slider[0].value)
        past=at.dataframe[0].value
        assert (past.position < pos).all()
        checks.append(f'{dataset}: {page}, cutoff={pos}, future labels hidden')
Path(__file__).with_name('dashboard_test_results.json').write_text(json.dumps({'status':'PASS','checks':checks},indent=2),encoding='utf-8')
print('\n'.join(checks))
