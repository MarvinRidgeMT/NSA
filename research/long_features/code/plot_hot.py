import json, math, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LightSource
from pathlib import Path
from polaris_batch import core
exec(open("plots.py").read().split("# Fig 1")[0])
import step4_hotspots as s4
fig,axs=plt.subplots(1,2,figsize=(12,6.2))
for ax,key in zip(axs,("Site04_ROI3","Site01_ROI6")):
    site,lat,lon=s4.R[key]
    sc,obs=s4.scores(key); ys=sc["year"]
    near=core.Dem.open(core.site_files(site,s4.D)["surf"][1])
    R0,C0=obs; H=30
    z=near.z[R0-H:R0+H+1,C0-H:C0+H+1]
    ls=LightSource(azdeg=315,altdeg=35); ax.imshow(ls.hillshade(z,vert_exag=3,dx=5,dy=5),cmap="gray",extent=(-H*5-2.5,H*5+2.5,-H*5-2.5,H*5+2.5),alpha=.75)
    vals=[(r,c,v) for r,c,v in ys["all_cells"] if v>0.05]
    vmax=max(v for *_,v in vals)
    for i,(r,c,v) in enumerate(vals):
        x=(c-C0)*5; y=-(r-R0)*5
        a=min(1,.25+.75*v/vmax)
        ax.add_patch(plt.Rectangle((x-2.5,y-2.5),5,5,color=SUN,alpha=a,lw=0))
        if i<10: ax.add_patch(plt.Rectangle((x-2.5,y-2.5),5,5,fill=False,ec="#FFFFFF",lw=.8))
    ax.add_patch(plt.Rectangle((-2.5,-2.5),5,5,fill=False,ec=TEAL,lw=1.6))
    ax.annotate(f"lander cell: {ys['observer_cell']['expected_flip_hours_removed']:.0f} h/yr",(0,-4),(0,-40),color=TEAL,fontsize=8.5,ha="center",bbox=dict(boxstyle="round,pad=0.25",fc="#05080F",ec="none",alpha=.85),arrowprops=dict(arrowstyle="-",color=TEAL,lw=.8))
    ax.set_xlim(-H*5,H*5); ax.set_ylim(-H*5,H*5); ax.set_xlabel("m (grid east)"); ax.set_ylabel("m (grid north)")
    ax.set_title(f"{key.replace('_',' ')}: Information Hotspots, 1 m mast, 12 months\nexpected Sun flip-hours removed if a 5 m cell is measured to 0.05 m",loc="left",fontsize=9.5)
    tot=ys["expected_flip_hours_total"]; ax.text(-H*5+4,H*5-10,f"total expected flip-hours/yr: {tot:.0f}\nwhite outline = top 10 cells",fontsize=8,color="#E6E9EF",va="top")
fig.text(0.01,0.01,"Linearised horizon + NASA PGDA 78 'toterr' sigma (pixels independent). SOURCE-BASED pilot, UNVALIDATED. Grid axes are polar-stereographic, not local north.",fontsize=7.5,color="#9AA3B2")
fig.tight_layout(rect=(0,.03,1,1)); fig.savefig("out/information_hotspots.png",dpi=150); print("ok")
