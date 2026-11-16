import json, numpy as np
from scipy.optimize import minimize
D=json.load(open('nac_results.json'))
out={}
for an in ('A_site01_roi6','B_site04_west'):
    M=[];O=[];IMG=[]
    n_img=0
    for img,v in D['images'].items():
        if an not in v: continue
        n_img+=1
        M+=v[an]['margin']; O+=v[an]['obs']; IMG+=[img]*len(v[an]['obs'])
    m=np.array(M); o=np.array(O)=='L'; p=m>0
    def stats(sel):
        tp=int(np.sum(p[sel]&o[sel])); tn=int(np.sum(~p[sel]&~o[sel])); fp=int(np.sum(p[sel]&~o[sel])); fn=int(np.sum(~p[sel]&o[sel]))
        n=tp+tn+fp+fn; acc=(tp+tn)/n
        sens=tp/max(1,tp+fn); spec=tn/max(1,tn+fp); bal=(sens+spec)/2
        pe=((tp+fp)*(tp+fn)+(tn+fn)*(tn+fp))/n**2; kappa=(acc-pe)/(1-pe) if pe<1 else float('nan')
        return dict(n=n,pred_lit_obs_lit=tp,pred_shadow_obs_shadow=tn,pred_lit_obs_shadow=fp,pred_shadow_obs_lit=fn,
                    obs_shadow=int(np.sum(~o[sel])),agreement=round(acc,4),balanced_accuracy=round(bal,4),kappa=round(kappa,4),
                    lit_recall=round(sens,4),shadow_recall=round(spec,4))
    allsel=np.ones(len(m),bool); nc=np.abs(m)>=0.5
    # logistic fit of P(obs lit) vs margin, on all points (crossing = horizon offset)
    def nll(t):
        a,b=t; z=np.clip((m-a)/abs(b),-50,50); q=1/(1+np.exp(-z)); q=np.clip(q,1e-9,1-1e-9); return -np.sum(o*np.log(q)+(~o)*np.log(1-q))
    r=minimize(nll,[0.0,0.3],method='Nelder-Mead')
    bins=np.arange(-3,3.01,0.25); tab=[]
    for lo in bins[:-1]:
        s=(m>=lo)&(m<lo+0.25)
        if s.sum(): tab.append((round(lo,2),int(s.sum()),round(float(o[s].mean()),3)))
    st_nc=stats(nc)
    passed=(st_nc['obs_shadow']>=200) and (st_nc['balanced_accuracy']>=0.90) and (abs(r.x[0])<=0.5)
    out[an]=dict(images=n_img, points_compared=int(len(m)), all=stats(allsel), excl_near_critical=st_nc,
                 crossing_deg=round(float(r.x[0]),3), crossing_width_deg=round(float(abs(r.x[1])),3), margin_bins=tab, area_pass=bool(passed))
    print('=====',an,'images',n_img); print(' all ',out[an]['all']); print(' excl',st_nc); print(' crossing %.3f deg width %.3f'%(r.x[0],abs(r.x[1])),' PASS' if passed else ' not pass')
    for t in tab: print('   ',t)
out['verdict']='PASS' if all(out[a]['area_pass'] for a in ('A_site01_roi6','B_site04_west')) else 'NOT PASS'
print(out['verdict'])
json.dump(out,open('nac_summary.json','w'),indent=1)
