import csv
import io
import math

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw, ImageOps
from streamlit_image_coordinates import streamlit_image_coordinates

st.set_page_config(page_title="NE111 Plot Digitizer", layout="wide")
st.title("Plot Digitizer")
st.caption("Calibrate the axes, click points, and export the coordinates.")


def reset():
    st.session_state.calibration = []
    st.session_state.datasets = {"Dataset 1": []}
    st.session_state.selected = "Dataset 1"
    st.session_state.last_click = None


if "calibration" not in st.session_state:
    reset()

uploaded = st.file_uploader("Upload graph image", type=["png", "jpg", "jpeg", "gif", "tif", "tiff"])
if uploaded is None:
    st.info("Upload an image to begin.")
    st.stop()

raw = uploaded.getvalue()
identity = (uploaded.name, len(raw), hash(raw))
if st.session_state.get("image_identity") != identity:
    reset()
    st.session_state.image_identity = identity

image = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")

with st.sidebar:
    st.header("Axes")
    xlabel = st.text_input("X-axis label", "x")
    ylabel = st.text_input("Y-axis label", "y")
    xmode = st.selectbox("X-axis scale", ["Linear", "Logarithmic"])
    ymode = st.selectbox("Y-axis scale", ["Linear", "Logarithmic"])
    x0 = st.number_input("X at origin", value=0.0)
    x1 = st.number_input("X at x reference", value=10.0)
    y0 = st.number_input("Y at origin", value=0.0)
    y1 = st.number_input("Y at y reference", value=10.0)
    if st.button("Reset calibration"):
        st.session_state.calibration = []
        st.session_state.last_click = None
        st.rerun()
    st.header("Datasets")
    new_name = st.text_input("New dataset name")
    if st.button("Add dataset"):
        name = new_name.strip()
        if not name or name in st.session_state.datasets:
            st.warning("Enter a unique dataset name.")
        else:
            st.session_state.datasets[name] = []
            st.session_state.selected = name
            st.rerun()
    st.session_state.selected = st.selectbox("Active dataset", list(st.session_state.datasets), index=list(st.session_state.datasets).index(st.session_state.selected))
    if st.button("Undo last point"):
        points = st.session_state.datasets[st.session_state.selected]
        if points:
            points.pop()
            st.rerun()
    if st.button("Delete active dataset"):
        if len(st.session_state.datasets) == 1:
            st.warning("Keep at least one dataset.")
        else:
            del st.session_state.datasets[st.session_state.selected]
            st.session_state.selected = next(iter(st.session_state.datasets))
            st.rerun()

if xmode == "Logarithmic" and (x0 <= 0 or x1 <= 0) or ymode == "Logarithmic" and (y0 <= 0 or y1 <= 0):
    st.error("Logarithmic axis reference values must be positive.")
    st.stop()

st.write("Click the **origin**, then a point on the **positive x-axis**, then a point on the **positive y-axis**. After that, click data points.")
colors = ["#e63946", "#0077b6", "#2a9d8f", "#8338ec", "#ff9f1c", "#e76f51"]
canvas = image.copy()
draw = ImageDraw.Draw(canvas)
for i, point in enumerate(st.session_state.calibration):
    px, py = point
    draw.ellipse((px-6, py-6, px+6, py+6), fill="#ffcc00", outline="black", width=2)
    draw.text((px+9, py-12), ["O", "X", "Y"][i], fill="black", stroke_width=2, stroke_fill="white")
for i, (name, points) in enumerate(st.session_state.datasets.items()):
    color = colors[i % len(colors)]
    for px, py in points:
        draw.ellipse((px-5, py-5, px+5, py+5), fill=color, outline="white", width=2)

# Display at original resolution so returned click coordinates match pixel coordinates.
click = streamlit_image_coordinates(canvas, key="graph_click")
if click is not None:
    pos = (int(click["x"]), int(click["y"]))
    # Widget keeps its last click through reruns; only consume a new click value.
    click_id = (pos, click.get("unix_time"))
    if click_id != st.session_state.last_click:
        st.session_state.last_click = click_id
        if len(st.session_state.calibration) < 3:
            st.session_state.calibration.append(pos)
        else:
            st.session_state.datasets[st.session_state.selected].append(pos)
        st.rerun()

st.caption(f"Calibration: {len(st.session_state.calibration)}/3 points selected")


def coordinates(pixel):
    o, xp, yp = [np.array(p, dtype=float) for p in st.session_state.calibration]
    basis = np.column_stack((xp-o, yp-o))
    if abs(np.linalg.det(basis)) < 1e-8:
        raise ValueError("Calibration points must not lie on the same line.")
    u, v = np.linalg.solve(basis, np.array(pixel, dtype=float)-o)
    def interpolate(a, b, t, mode):
        if mode == "Logarithmic":
            return float(np.exp(np.log(a) + t*(np.log(b)-np.log(a))))
        return float(a + t*(b-a))
    return interpolate(x0, x1, u, xmode), interpolate(y0, y1, v, ymode)


if len(st.session_state.calibration) == 3:
    try:
        coordinates(st.session_state.calibration[0])
        st.subheader("Extracted data")
        tables = {}
        for name, points in st.session_state.datasets.items():
            tables[name] = [coordinates(p) for p in points]
            st.write(f"**{name}**")
            st.dataframe(pd.DataFrame(tables[name], columns=[xlabel, ylabel]), hide_index=True)
        output = io.StringIO()
        writer = csv.writer(output)
        names = list(tables)
        writer.writerow([part for name in names for part in (name, "")])
        writer.writerow([part for _ in names for part in (xlabel, ylabel)])
        longest = max((len(points) for points in tables.values()), default=0)
        for j in range(longest):
            row = []
            for name in names:
                row.extend(tables[name][j] if j < len(tables[name]) else ("", ""))
            writer.writerow(row)
        st.download_button("Download CSV", output.getvalue(), "digitized_data.csv", "text/csv")
    except ValueError as exc:
        st.error(str(exc))
