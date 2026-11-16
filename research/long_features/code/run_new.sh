set -x
cd /home/claude/pb
python3 jobs.py work/jobs_N.json 2
export SITES=Site07_ROI1,Site11_ROI4
python3 step3_rq2.py
NOTEST=1 python3 step4_hotspots.py
python3 step5_strip.py
python3 step5b_slip.py
python3 step7_replay.py
python3 step8_sky.py
python3 step9_lens.py
python3 step12_more.py
python3 step13_asset.py
python3 step18_hot_corr.py Site07_ROI1,Site11_ROI4
echo ALLDONE
