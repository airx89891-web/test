import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import plotly.graph_objects as go
import math
import io

st.title("Wafer Die Map Editor (Multi-Type Support)")

# --- Upload XML file ---
uploaded_file = st.file_uploader("Upload XML file", type=["xml"])
if uploaded_file:
    tree = ET.parse(uploaded_file)
    root = tree.getroot()
    ns = {'ns': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}

    st.success("XML file loaded successfully!")

    # --- Wafer Size ---
    wafer_size_mm = st.number_input("Wafer Size (mm)", value=300.0)
    wafer_radius_um = wafer_size_mm * 1000 / 2

    # --- Die Type Settings ---
    st.subheader("Die Type Settings")
    die_types = st.session_state.get("die_types", [])

    if st.button("Add Die Type"):
        die_types.append({"Type Name": f"Type {len(die_types)+1}",
                          "Die Size X (µm)": 46730, "Die Size Y (µm)": 35420,
                          "Offset X (µm)": 0, "Offset Y (µm)": 0})
        st.session_state["die_types"] = die_types

    if die_types:
        df_die_types = pd.DataFrame(die_types)
        edited_df = st.data_editor(df_die_types, num_rows="dynamic")
        st.session_state["die_types"] = edited_df.to_dict("records")

    # --- Assign Die Types ---
    st.subheader("Assign Die Types to Traversal Index Range")
    type_mapping = {}
    for die_type in st.session_state.get("die_types", []):
        start = st.number_input(f"{die_type['Type Name']} Start Index", value=1)
        end = st.number_input(f"{die_type['Type Name']} End Index", value=10)
        type_mapping[die_type['Type Name']] = (start, end)

    # --- Update XML and Visualization ---
    if st.button("Update XML and Visualize"):
        die_data = []
        for die in root.findall('.//DieList', ns):
            origin = die.find('DieOrigin', ns)
            measure_enable = die.find('DieMeasureEnable', ns)
            traversal_index = die.find('DieTraversalIndex', ns)
            if origin is not None and measure_enable is not None and traversal_index is not None:
                x = origin.find('CoordinateX/Value', ns)
                y = origin.find('CoordinateY/Value', ns)
                if x is not None and y is not None:
                    die_id = int(traversal_index.text)
                    # Find matching die type
                    selected_type = None
                    for t_name, (start, end) in type_mapping.items():
                        if start <= die_id <= end:
                            selected_type = next(dt for dt in st.session_state["die_types"] if dt["Type Name"] == t_name)
                            break
                    if not selected_type:
                        selected_type = st.session_state["die_types"][0]  # default

                    die_size_x = selected_type["Die Size X (µm)"]
                    die_size_y = selected_type["Die Size Y (µm)"]
                    offset_x = selected_type["Offset X (µm)"]
                    offset_y = selected_type["Offset Y (µm)"]

                    center_x = int(x.text) + die_size_x // 2 + offset_x
                    center_y = int(y.text) + die_size_y // 2 + offset_y

                    x.text = str(center_x)
                    y.text = str(center_y)

                    die_data.append({
                        "X": center_x,
                        "Y": center_y,
                        "DieID": die_id,
                        "Type": selected_type["Type Name"]
                    })

        # Save updated XML
        xml_bytes = io.BytesIO()
        tree.write(xml_bytes, encoding="utf-8", xml_declaration=True)
        st.download_button("Download Updated XML", data=xml_bytes.getvalue(),
                           file_name="updated_die_map.xml", mime="application/xml")

        # Visualization
        df = pd.DataFrame(die_data)
        scatter = go.Scatter(
            x=df["X"], y=df["Y"], mode="markers+text", text=df["DieID"],
            textposition="top center",
            marker=dict(color=df["Type"], size=8),
            name="Dies"
        )

        # Wafer outline
        circle_x = [wafer_radius_um * math.cos(theta) for theta in [i * math.pi / 180 for i in range(0, 361)]]
        circle_y = [wafer_radius_um * math.sin(theta) for theta in [i * math.pi / 180 for i in range(0, 361)]]
        circle = go.Scatter(x=circle_x, y=circle_y, mode="lines", line=dict(color="black", width=2), name="Wafer")

        # Grid lines (based on first type for simplicity)
        die_size_x = st.session_state["die_types"][0]["Die Size X (µm)"]
        die_size_y = st.session_state["die_types"][0]["Die Size Y (µm)"]
        x_min, x_max = df["X"].min(), df["X"].max()
        y_min, y_max = df["Y"].min(), df["Y"].max()
        vertical_lines = [
            go.Scatter(x=[x, x], y=[y_min, y_max], mode="lines",
                       line=dict(color="gray", width=1, dash="dot"), showlegend=False)
            for x in range(int(x_min - die_size_x), int(x_max + die_size_x), die_size_x)
        ]
        horizontal_lines = [
            go.Scatter(x=[x_min, x_max], y=[y, y], mode="lines",
                       line=dict(color="gray", width=1, dash="dot"), showlegend=False)
            for y in range(int(y_min - die_size_y), int(y_max + die_size_y), die_size_y)
        ]

        fig = go.Figure(data=[scatter, circle] + vertical_lines + horizontal_lines)
        fig.update_layout(title="Die Map Visualization (Multi-Type)", xaxis=dict(scaleanchor="y", scaleratio=1))
