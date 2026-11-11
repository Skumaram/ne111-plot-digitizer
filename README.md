# NE111 Plot Digitizer

A single-page Streamlit plot digitizer.

## Run locally

```bash
uv init --bare  # only if you do not already have a pyproject.toml
uv add streamlit streamlit-image-coordinates pillow numpy pandas
uv run streamlit run app.py
```

Alternatively, `pip install -r requirements.txt` and `streamlit run app.py`.

## How to use

1. Upload a graph image.
2. Set the axis labels, scale types, and values at the origin and reference points.
3. Click origin, x-axis reference, and y-axis reference in that order.
4. Click graph points, switch datasets as needed, and export CSV.

The three-point affine calibration supports rotated and skewed axes. Log axes require positive reference values.

## Limitations / next improvements

- Zoom is not implemented.
- Editing table cells to reposition markers is not implemented.
- Clicking the same pixel twice may not register, depending on the widget event timestamp.
- The Streamlit Cloud deployment needs to be tested with the hosted package versions.
