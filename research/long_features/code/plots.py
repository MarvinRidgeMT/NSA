import json, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt, matplotlib.dates as mdates
from datetime import datetime
plt.rcParams.update({"font.family":"Inter","font.size":10,"axes.facecolor":"#0B1426","figure.facecolor":"#05080F","text.color":"#E6E9EF",
  "axes.labelcolor":"#C9CED8","xtick.color":"#9AA3B2","ytick.color":"#9AA3B2","axes.edgecolor":"#2A3550","grid.color":"#1C2740"})
SUN,EARTH,TEAL,FAIL="#F2B33D","#4A90E2","#2EC4B6","#E5484D"
def dt(s): return datetime.strptime(s,"%Y-%b-%d %H:%M")
# Fig 1: 12-month strip
fig,axs=plt.subplots(4,1,figsize=(12,8.2),sharex=True,gridspec_kw={"height_ratios":[3,.35,3,.35]})
for i,key in enumerate(("Site04_ROI3","Site01_ROI6")):
    z=np.load(f"work/strip/strip_{key}.npz"); t=[dt(s) for s in z["starts"]]
    ax=axs[2*i]; ax.fill_between(t,z["cl_sun"].min(0),z["cl_sun"].max(0),color=SUN,alpha=.28,lw=0,label="Sun, 20 clones (min–max)")
    ax.plot(t,z["nom_sun"],color=SUN,lw=1.2,label="Sun, nominal DEM")
    ax.fill_between(t,z["cl_both"].min(0),z["cl_both"].max(0),color=EARTH,alpha=.25,lw=0,label="Sun+Earth, 20 clones")
    ax.plot(t,z["nom_both"],color=EARTH,lw=1.0,label="Sun+Earth, nominal")
    ax.axhline(70,color=SUN,ls=(0,(4,3)),lw=.8); ax.axhline(40,color=EARTH,ls=(0,(4,3)),lw=.8)
    ax.set_ylim(0,101); ax.set_ylabel("% of 14-day mission"); ax.grid(axis="y",lw=.5)
    ax.set_title(f"{key.replace('_',' ')}  ·  1 m mast  ·  every hourly 14-day mission start, 14 Nov 2026 → 14 Nov 2027",loc="left",fontsize=10.5,color="#E6E9EF")
    if i==0: fig.legend(*ax.get_legend_handles_labels(),loc="upper center",fontsize=8.5,frameon=False,ncol=4)
    ps=z["pass_sun"]; col=np.where(ps==20,TEAL,np.where(ps==0,FAIL,"#8C7AE6"))
    b=axs[2*i+1]; b.bar(t,1,width=1/24,color=col,lw=0); b.set_yticks([]); b.set_ylim(0,1)
    b.set_ylabel("Sun ≥70 %",rotation=0,ha="right",va="center",fontsize=8)
axs[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
fig.text(0.01,0.005,"Pass strip: teal = all 20 clones pass · violet = clones disagree · red = no clone passes.  Dashed: team thresholds 70 % / 40 %.  SOURCE-BASED, UNVALIDATED. Geometric visibility of the Sun/Earth centre only. k/20 is not a probability.",fontsize=7.5,color="#9AA3B2")
fig.tight_layout(rect=(0,.02,1,.965)); fig.savefig("out/window_strip_12mo.png",dpi=150)
# Fig 2: slip
s=json.load(open("work/strip/slip_pm7d.json"))
fig,axs=plt.subplots(2,1,figsize=(11,6),sharex=True)
for ax,key in zip(axs,("Site04_ROI3","Site01_ROI6")):
    r=s[key]; h=np.array([x["slip_h"] for x in r])/24
    ax.fill_between(h,[x["sun_min"] for x in r],[x["sun_max"] for x in r],color=SUN,alpha=.3,lw=0,label="Sun, 20 clones (min–max)")
    ax.plot(h,[x["sun_nom"] for x in r],color=SUN,lw=1.4,label="Sun, nominal")
    ax.plot(h,[x["both_min"] for x in r],color=EARTH,lw=1,ls=":",label="Sun+Earth, worst clone")
    ax.axhline(70,color=SUN,ls=(0,(4,3)),lw=.8); ax.axvline(0,color="#E6E9EF",lw=.8)
    bad=[x["slip_h"]/24 for x in r if x["pass_sun70"]<20]
    if bad: ax.axvspan(min(bad),max(h),color=FAIL,alpha=.12,lw=0,label="some clone < 70 % Sun")
    ax.set_ylim(0,101); ax.grid(lw=.4); ax.set_ylabel("% of 14-day mission")
    ax.set_title(f"{key.replace('_',' ')}: arrival slip around the demo start (14 Nov 2026 00:00 UTC), 1 m mast",loc="left",fontsize=10.5)
    ax.legend(loc="lower left",fontsize=8,frameon=False,ncol=4)
axs[-1].set_xlabel("start slip (days)")
fig.text(0.01,0.005,"SOURCE-BASED, UNVALIDATED. Clone band = 20 PGDA 78 terrain clones (vertical error model on the 5 m tile only).",fontsize=7.5,color="#9AA3B2")
fig.tight_layout(rect=(0,.02,1,1)); fig.savefig("out/arrival_slip_pm7d.png",dpi=150)
print("ok")
