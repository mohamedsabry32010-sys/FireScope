import streamlit as st, pandas as pd, numpy as np, requests, folium
from streamlit_folium import st_folium
import plotly.express as px
from datetime import date
from io import StringIO
from scipy.spatial import cKDTree

st.set_page_config(page_title="FireScope | NASA Fire Intelligence",page_icon="🔥",layout="wide")
st.markdown("""<style>
.stApp{background:#0b1420;color:#eaf1f7}.hero{padding:25px;border:1px solid #29435b;border-radius:18px;background:linear-gradient(120deg,#14283b,#28394b)}
.kpi{background:#142335;border:1px solid #2b4054;border-radius:14px;padding:14px}
div[data-testid="stMetric"]{background:#142335;padding:12px;border:1px solid #2b4054;border-radius:12px}
.note{background:#1a2b3c;padding:12px;border-left:4px solid #e89a39;border-radius:8px}
</style>""",unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>🔥 FireScope</h1><b>NASA Fire Intelligence</b><br>MODIS + VIIRS • Interactive exploration, sensor comparison and unusual-activity analysis</div>',unsafe_allow_html=True)
st.caption("Exploratory prototype. Satellite hotspots are not confirmed fire perimeters and this app does not predict future fires.")

def demo():
 r=np.random.default_rng(19);n=350;s=r.choice(["VIIRS","MODIS"],n,p=[.7,.3]);d=pd.Timestamp.today().normalize()-pd.to_timedelta(r.integers(0,30,n),unit="D")
 return pd.DataFrame({"latitude":r.uniform(-34,37,n),"longitude":r.uniform(-17,52,n),"acq_date":d.strftime("%Y-%m-%d"),"satellite":s,"confidence":r.choice(["l","n","h"],n,p=[.15,.55,.3]),"frp":r.gamma(2,8,n).round(1),"brightness":r.normal(330,20,n).round(1),"acq_time":r.integers(0,2400,n),"daynight":r.choice(["D","N"],n)})
def norm(d):
 d=d.copy();d.columns=[str(c).lower() for c in d.columns]
 for old,new in [("lat","latitude"),("lon","longitude"),("lng","longitude"),("sensor","satellite")]:
  if old in d and new not in d:d.rename(columns={old:new},inplace=True)
 for c in ["latitude","longitude"]:
  if c not in d:raise ValueError("CSV must contain latitude and longitude columns.")
  d[c]=pd.to_numeric(d[c],errors="coerce")
 d=d.dropna(subset=["latitude","longitude"])
 defaults={"acq_date":date.today().isoformat(),"satellite":"Unknown","confidence":"n","frp":np.nan,"brightness":np.nan,"acq_time":np.nan,"daynight":"?"}
 for c,v in defaults.items():
  if c not in d:d[c]=v
 d["acq_date"]=pd.to_datetime(d.acq_date,errors="coerce").dt.strftime("%Y-%m-%d")
 d["satellite"]=d.satellite.astype(str).str.upper().replace({"NOAA-20":"VIIRS","NOAA-21":"VIIRS","SUOMI-NPP":"VIIRS","TERRA":"MODIS","AQUA":"MODIS"})
 d["frp"]=pd.to_numeric(d.frp,errors="coerce")
 return d
def firms(key,src,area,days):
 u=f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{src}/{area}/{days}"
 q=requests.get(u,timeout=40);q.raise_for_status()
 if "Invalid MAP_KEY" in q.text:raise ValueError("NASA rejected the MAP_KEY.")
 return norm(pd.read_csv(StringIO(q.text)))
st.sidebar.title("Data control")
mode=st.sidebar.radio("Data source",["Demo data","NASA FIRMS API","Upload FIRMS CSV"])
key=st.sidebar.text_input("NASA FIRMS MAP_KEY",type="password")
src=st.sidebar.selectbox("Product",["VIIRS_NOAA20_NRT","VIIRS_NOAA21_NRT","VIIRS_SNPP_NRT","MODIS_NRT","VIIRS_SNPP_SP"])
area=st.sidebar.text_input("Bounding box west,south,east,north","-17,-35,52,38")
days=st.sidebar.slider("Look-back days",1,10,3)
upload=st.sidebar.file_uploader("FIRMS CSV",type="csv")
try:
 if mode=="NASA FIRMS API":
  if key: df=firms(key,src,area,days);st.sidebar.success(f"{len(df)} rows loaded")
  else:df=demo();st.info("Enter your free NASA FIRMS MAP_KEY in the sidebar. Demo data shown until then.")
 elif mode=="Upload FIRMS CSV":
  df=norm(pd.read_csv(upload)) if upload else demo()
  if not upload:st.info("Upload a FIRMS CSV; showing demo data meanwhile.")
 else:df=demo();st.info("Demo dataset is synthetic. Connect NASA FIRMS or upload real data for scientific analysis.")
except Exception as e:st.error(f"Data loading error: {e}");df=demo()
st.sidebar.markdown("### Filters")
sensors=st.sidebar.multiselect("Sensors",sorted(df.satellite.unique()),default=sorted(df.satellite.unique()))
confs=st.sidebar.multiselect("Confidence",sorted(df.confidence.astype(str).unique()),default=sorted(df.confidence.astype(str).unique()))
f=df[df.satellite.isin(sensors)&df.confidence.astype(str).isin(confs)].copy()
f["date"]=pd.to_datetime(f.acq_date,errors="coerce")
f["day"]=f.date.dt.strftime("%Y-%m-%d")
t1,t2,t3,t4,t5=st.tabs(["🗺️ Fire map","🛰️ MODIS vs VIIRS","📅 Calendar","📊 Analytics","📄 Reports"])
with t1:
 a,b,c=st.columns(3);a.metric("Total detections",f"{len(f):,}");b.metric("MODIS",int(f.satellite.str.contains("MODIS").sum()));c.metric("VIIRS",int(f.satellite.str.contains("VIIRS").sum()))
 if len(f):
  m=folium.Map([f.latitude.mean(),f.longitude.mean()],zoom_start=4,tiles="CartoDB dark_matter")
  for _,x in f.head(5000).iterrows():
   color="#ffb347" if "MODIS" in x.satellite else "#ff554f" if "VIIRS" in x.satellite else "#64b5cd"
   folium.CircleMarker([x.latitude,x.longitude],radius=4,color=color,fill=True,fill_opacity=.8,popup=f"{x.satellite} | {x.acq_date} | confidence {x.confidence} | FRP {x.frp} MW").add_to(m)
  st_folium(m,use_container_width=True,height=550)
  st.caption("Each marker is a satellite hotspot detection, not a mapped fire boundary. Map limited to 5,000 markers for performance.")
with t2:
 st.subheader("Exploratory cross-sensor comparison")
 mod=f[f.satellite.str.contains("MODIS")];vii=f[f.satellite.str.contains("VIIRS")]
 ma=unma=unv=0
 for day in set(mod.acq_date)&set(vii.acq_date):
  aa=mod[mod.acq_date==day];bb=vii[vii.acq_date==day]
  if len(aa) and len(bb):
   lat0=np.deg2rad(pd.concat([aa.latitude,bb.latitude]).mean())
   xy=lambda z:np.c_[z.longitude*111.32*np.cos(lat0),z.latitude*111.32]
   dist,idx=cKDTree(xy(bb)).query(xy(aa),distance_upper_bound=1.0)
   pairs=[(i,j) for i,j in enumerate(idx) if j<len(bb) and dist[i]<=1]
   ma+=len(set(i for i,j in pairs));unma+=len(aa)-len(set(i for i,j in pairs));unv+=len(bb)-len(set(j for i,j in pairs))
 x,y,z=st.columns(3);x.metric("Approx. matched MODIS",ma);y.metric("MODIS unmatched",unma);z.metric("VIIRS unmatched",unv)
 st.markdown('<div class="note">Approximate match = same acquisition date and within ~1 km. This is an exploratory rule, not formal validation. MODIS and VIIRS differ in pixel size, overpass time, viewing geometry and geolocation uncertainty.</div>',unsafe_allow_html=True)
 if len(f):st.plotly_chart(px.histogram(f,x="satellite",color="satellite",title="Detections by sensor"),use_container_width=True)
with t3:
 st.subheader("Observed fire activity")
 if len(f):
  daily=f.groupby("day").size().reset_index(name="detections")
  st.plotly_chart(px.bar(daily,x="day",y="detections",title="Daily hotspot detections"),use_container_width=True)
  st.dataframe(daily.sort_values("day",ascending=False),use_container_width=True,hide_index=True)
with t4:
 st.subheader("Unusual activity detection")
 if len(f):
  daily=f.groupby("day").size().reset_index(name="detections").sort_values("day")
  if len(daily)>=3:
   avg=daily.detections.mean();sd=daily.detections.std(ddof=0);threshold=avg+2*sd
   daily["unusual_activity"]=daily.detections>threshold
   st.metric("Average detections per observed day",f"{avg:.1f}");st.metric("Exploratory threshold (mean + 2 SD)",f"{threshold:.1f}")
   st.plotly_chart(px.bar(daily,x="day",y="detections",color="unusual_activity",title="Observed counts and unusual-activity flags"),use_container_width=True)
   st.dataframe(daily,use_container_width=True,hide_index=True)
  else:st.info("At least three observed dates are needed for this simple baseline.")
  if f.frp.notna().any():
   st.metric("Sum of reported FRP",f"{f.frp.sum():,.1f} MW")
   st.plotly_chart(px.histogram(f.dropna(subset=["frp"]),x="frp",color="satellite",title="Fire Radiative Power distribution"),use_container_width=True)
 st.caption("Flags indicate unusually high counts in the selected dataset only. They are not forecasts, verified fire events, or risk predictions.")
with t5:
 st.subheader("Report builder & exports")
 report=f"""FIRESCOPE — NASA FIRMS EXPLORATORY REPORT
Generated: {date.today()}
Records: {len(f)}
Sensors: {', '.join(sensors)}
Confidence filters: {', '.join(confs)}
Date range: {f.acq_date.min() if len(f) else 'N/A'} to {f.acq_date.max() if len(f) else 'N/A'}
MODIS: {int(f.satellite.str.contains('MODIS').sum())}
VIIRS: {int(f.satellite.str.contains('VIIRS').sum())}
Mean FRP MW: {f.frp.mean() if len(f) and f.frp.notna().any() else 'N/A'}

Limitations: hotspot detections are not confirmed ground fires or fire perimeters. Sensor timing, resolution, clouds and confidence affect detections. This report does not predict future fires."""
 st.text_area("Report preview",report,height=240)
 st.download_button("⬇ Download report TXT",report,"FireScope_report.txt")
 st.download_button("⬇ Download filtered detections CSV",f.to_csv(index=False),"FireScope_detections.csv","text/csv")
 st.dataframe(f.head(1000),use_container_width=True,hide_index=True)
st.divider()
st.markdown("**Scientific interpretation & limitations**")
st.write("FIRMS active-fire products identify thermal anomalies at satellite overpass times. Cloud cover, smoke, viewing angle, pixel size, algorithm confidence and overpass timing affect observations. A detection is not automatically a confirmed wildfire. This app analyzes observed records; it does not forecast future fires.")
