import csv
import io
import hashlib
import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title='NE111 Plot Digitizer', layout='wide')
st.title('Plot Digitizer')
st.caption('Calibrate your graph, extract data, and export CSV files.')
s = st.session_state

def reset_click():
    s.widget_version = s.get('widget_version', 0) + 1
    s.last_click = None

def refresh_editor():
    s.editor_version = s.get('editor_version', 0) + 1

uploaded = st.file_uploader('Upload graph image', type=['png','jpg','jpeg','gif','tif','tiff'])
if uploaded is None:
    st.info('Upload an image to begin.')
    st.stop()
raw = uploaded.getvalue()
identity = (uploaded.name, hashlib.sha256(raw).hexdigest())
if s.get('image_identity') != identity:
    s.image_identity = identity
    s.calibration = []
    s.datasets = {'Dataset 1': []}
    s.selected = 'Dataset 1'
    reset_click()
    refresh_editor()
image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert('RGB')
with st.sidebar:
    st.header('Axes')
    xlabel = st.text_input('X-axis label', 'x')
    ylabel = st.text_input('Y-axis label', 'y')
    xmode = st.selectbox('X-axis scale', ['Linear','Logarithmic'])
    ymode = st.selectbox('Y-axis scale', ['Linear','Logarithmic'])
    x0 = st.number_input('X at origin', value=0.0)
    x1 = st.number_input('X at x reference', value=10.0)
    y0 = st.number_input('Y at origin', value=0.0)
    y1 = st.number_input('Y at y reference', value=10.0)
    if st.button('Reset calibration'):
        s.calibration = []
        reset_click()
        refresh_editor()
        st.rerun()
    if st.button('Undo calibration point') and s.calibration:
        s.calibration.pop()
        reset_click()
        refresh_editor()
        st.rerun()
    st.header('Datasets')
    name = st.text_input('New dataset name').strip()
    if st.button('Add dataset'):
        if not name or name in s.datasets:
            st.warning('Enter a unique dataset name.')
        else:
            s.datasets[name] = []
            s.selected = name
            st.rerun()
    s.selected = st.selectbox('Active dataset', list(s.datasets), index=list(s.datasets).index(s.selected))
    points = s.datasets[s.selected]
    if st.button('Undo last point') and points:
        points.pop()
        refresh_editor()
        st.rerun()
    if points:
        index = st.selectbox('Point to delete', range(len(points)), format_func=lambda i: f'Point {i+1}')
        if st.button('Delete selected point'):
            points.pop(index)
            refresh_editor()
            st.rerun()
    if st.button('Delete active dataset'):
        if len(s.datasets) == 1:
            points.clear()
        else:
            del s.datasets[s.selected]
            s.selected = next(iter(s.datasets))
        refresh_editor()
        st.rerun()
    st.header('Display')
    zoom = st.slider('Image zoom (%)', 50, 300, 100, 25)

if (xmode == 'Logarithmic' and min(x0,x1) <= 0) or (ymode == 'Logarithmic' and min(y0,y1) <= 0):
    st.error('Logarithmic reference values must be positive.')
    st.stop()
if x0 == x1 or y0 == y1:
    st.error('Origin and reference values must differ.')
    st.stop()
settings = (xlabel,ylabel,xmode,ymode,x0,x1,y0,y1)
if s.get('settings') != settings:
    s.settings = settings
    refresh_editor()
if s.get('zoom') != zoom:
    s.zoom = zoom
    reset_click()

def basis():
    o, xp, yp = [np.array(p,dtype=float) for p in s.calibration]
    b = np.column_stack((xp-o,yp-o))
    if abs(np.linalg.det(b)) < 1e-8:
        raise ValueError('Calibration points must not lie on the same line.')
    return o,b

def interpolate(a,b,t,mode):
    if mode == 'Logarithmic':
        return float(np.exp(np.log(a)+t*(np.log(b)-np.log(a))))
    return float(a+t*(b-a))

def coordinates(pixel):
    o,b = basis()
    u,v = np.linalg.solve(b,np.array(pixel,dtype=float)-o)
    return interpolate(x0,x1,u,xmode),interpolate(y0,y1,v,ymode)

def fraction(a,b,value,mode):
    if not np.isfinite(value):
        raise ValueError('Enter finite coordinates.')
    if mode == 'Logarithmic':
        if value <= 0:
            raise ValueError('Logarithmic coordinates must be positive.')
        a,b,value = np.log([a,b,value])
    return (value-a)/(b-a)

def pixel_for(x,y):
    o,b = basis()
    p = o+b@np.array([fraction(x0,x1,x,xmode),fraction(y0,y1,y,ymode)])
    if not np.all(np.isfinite(p)) or not (0 <= p[0] < image.width and 0 <= p[1] < image.height):
        raise ValueError('Edited point must lie inside the image.')
    return tuple(p)

n = len(s.calibration)
st.info(['Click the origin (O).','Click the X reference on the horizontal axis.','Click the Y reference on the vertical axis.','Click data points on the graph.'][n])
st.progress(n/3, text=f'Calibration: {n}/3 points selected')
if n == 3:
    try:
        basis()
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
colors = ['#e63946','#0077b6','#2a9d8f','#8338ec','#ff9f1c','#e76f51']
w,h = max(1,round(image.width*zoom/100)),max(1,round(image.height*zoom/100))
sx,sy = w/image.width,h/image.height
canvas = image.resize((w,h),Image.Resampling.LANCZOS)
draw = ImageDraw.Draw(canvas)
def marker(p,color,r,label=None):
    x,y = p[0]*sx,p[1]*sy
    draw.ellipse((x-r,y-r,x+r,y+r),fill=color,outline='black' if label else 'white',width=2)
    if label:
        draw.text((x+9,y-12),label,fill='black',stroke_width=2,stroke_fill='white')
for i,p in enumerate(s.calibration):
    marker(p,'#ffcc00',6,['O','X','Y'][i])
for i,(name,points) in enumerate(s.datasets.items()):
    for p in points:
        marker(p,colors[i%len(colors)],5)
click = streamlit_image_coordinates(canvas,key=f'graph_{s.widget_version}')
if click is not None:
    pos = (click['x'],click['y'])
    click_id = (pos,click.get('unix_time'))
    if click_id != s.last_click:
        s.last_click = click_id
        p = (pos[0]/sx,pos[1]/sy)
        if 0 <= p[0] < image.width and 0 <= p[1] < image.height:
            if n < 3:
                s.calibration.append(p)
            else:
                s.datasets[s.selected].append(p)
            refresh_editor()
            st.rerun()
if n == 3:
    st.subheader('Extracted data')
    st.caption('Edit numerical coordinates to move markers on the graph.')
    tables = {}
    for i,(name,points) in enumerate(s.datasets.items()):
        values = [coordinates(p) for p in points]
        st.markdown(f'**{name}**')
        # Internal column names stay unique even if axis labels match.
        df = pd.DataFrame(values,columns=['x','y'],dtype=float)
        edited = st.data_editor(df, key=f'edit_{i}_{s.editor_version}',hide_index=True,num_rows='fixed',column_config={'x':st.column_config.NumberColumn(xlabel),'y':st.column_config.NumberColumn(ylabel)})
        if not edited.equals(df):
            try:
                updated = [pixel_for(float(x),float(y)) for x,y in edited.itertuples(index=False,name=None)]
                s.datasets[name] = updated
                refresh_editor()
                st.rerun()
            except (ValueError,TypeError) as exc:
                st.error(str(exc))
        tables[name] = values
    output = io.StringIO()
    writer = csv.writer(output)
    names = list(tables)
    writer.writerow([part for name in names for part in (name,'')])
    writer.writerow([part for _ in names for part in (xlabel,ylabel)])
    for j in range(max((len(v) for v in tables.values()),default=0)):
        row = []
        for name in names:
            row.extend(tables[name][j] if j < len(tables[name]) else ('',''))
        writer.writerow(row)
    st.download_button('Download CSV',output.getvalue(),'digitized_data.csv','text/csv')
