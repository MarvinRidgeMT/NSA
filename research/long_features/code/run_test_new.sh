set -x
cd /home/claude/pb
export SITES=Site07_ROI1,Site11_ROI4
python3 step4_hotspots.py
TRAIN=1-10 OUT=hot_corr_train.json python3 step18_hot_corr.py Site07_ROI1,Site11_ROI4
python3 step18c_oos.py Site07_ROI1
python3 step18c_oos.py Site11_ROI4
echo ALLDONE
