from datetime import datetime
import pandas as pd
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak
from reportlab.lib.units import inch
from io import BytesIO
import streamlit as st

# Functie om CSV-bestanden in te lezen
def read_csv(file):
    try:
        df = pd.read_csv(file, sep=None, engine='python', on_bad_lines='skip')
        st.write(f"Succesvol ingelezen: {file.name}")
        return df
    except Exception as e:
        st.error(f"Fout bij inlezen van {file.name}: {e}")
        return None

# Functie om footers met projectnamen en paginanummers toe te voegen aan de PDF
def add_page_number(canvas, doc, projectnaam1, projectnaam2):
    page_num = f"{projectnaam1} & {projectnaam2} | Page {doc.page}"
    canvas.saveState()
    canvas.setFont('Helvetica', 10)
    canvas.drawRightString(landscape(A4)[0] - 0.5*inch, 0.5*inch, page_num)
    canvas.restoreState()

# Functie om een sectie toe te voegen aan het document
def add_section(story, data, section_title, col_widths):
    story.append(Paragraph(section_title, getSampleStyleSheet()['Heading2']))
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, '#000000'),
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(table)
    story.append(PageBreak())

# Functie om de PDF te genereren met de juiste secties en footers
def create_pdf_with_correct_columns(sectie_1_data, sectie_2_data, sectie_3_data, projectnaam1, projectnaam2):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=0.25*inch, leftMargin=0.25*inch, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Titel van de PDF
    title = f"Materiaal overlap {projectnaam1} & {projectnaam2}"
    story.append(Paragraph(title, styles['Title']))

    total_width = landscape(A4)[0] - doc.leftMargin - doc.rightMargin
    col_widths = [0.5 * inch, 0.75 * inch, 7 * inch, 1 * inch, 1 * inch]  # Kolombreedtes

    # Schaal kolom breedtes om binnen de pagina te passen
    total_col_width = sum(col_widths)
    if total_col_width > total_width:
        scale_factor = total_width / total_col_width
        col_widths = [w * scale_factor for w in col_widths]

    sectie_1_data.insert(0, ["✓", "Aantal pakken", "Naam", f"Aantal {projectnaam1}", f"Aantal {projectnaam2}"])
    add_section(story, sectie_1_data, "Sectie 1: Blijft op locatie", col_widths)

    sectie_2_data.insert(0, ["✓", "Aantal pakken", "Naam", f"Aantal {projectnaam1}", f"Aantal {projectnaam2}"])
    add_section(story, sectie_2_data, "Sectie 2: Extra nodig", col_widths)

    sectie_3_data.insert(0, ["✓", "Aantal pakken", "Naam", f"Aantal {projectnaam1}", f"Aantal {projectnaam2}"])
    add_section(story, sectie_3_data, "Sectie 3: Te veel", col_widths)

    def on_page(canvas, doc):
        add_page_number(canvas, doc, projectnaam1, projectnaam2)

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    buffer.seek(0)
    return buffer

# Streamlit UI setup
st.title('Carnet Project Material Comparison Tool')

# Twee uploadvelden voor de projecten
uploaded_file_oldest = st.file_uploader("Upload CSV voor het oudste project (referentie)", type="csv", key="oldest")
uploaded_file_newest = st.file_uploader("Upload CSV voor het jongste project", type="csv", key="newest")

if uploaded_file_oldest and uploaded_file_newest:
    df_oldest = read_csv(uploaded_file_oldest)
    df_newest = read_csv(uploaded_file_newest)

    if df_oldest is not None and df_newest is not None:
        # Verwerk de bestandsnamen voor projectnamen en datums
        file_parts_oldest = uploaded_file_oldest.name.replace('.csv', '').split(" - ")
        file_parts_newest = uploaded_file_newest.name.replace('.csv', '').split(" - ")

        if len(file_parts_oldest) == 3 and len(file_parts_newest) == 3:
            projectnaam_oldest, datum_oldest = file_parts_oldest[1], file_parts_oldest[2]
            projectnaam_newest, datum_newest = file_parts_newest[1], file_parts_newest[2]

            try:
                # Converteer de datums naar datetime-objecten
                datum_oldest_dt = datetime.strptime(datum_oldest, '%d-%m-%Y')
                datum_newest_dt = datetime.strptime(datum_newest, '%d-%m-%Y')

                # Controleer of de bestanden in de juiste volgorde zijn geüpload
                if datum_oldest_dt > datum_newest_dt:
                    st.error("Het oudste project is later dan het jongste project. Zorg ervoor dat het oudste project in het eerste uploadveld wordt geüpload.")
                else:
                    # Controleer of de kolommen aanwezig zijn
                    if 'Amount' in df_oldest.columns and 'Naam (in database)' in df_oldest.columns:
                        df_1_filtered = df_oldest[['Amount', 'Naam (in database)']]
                        df_2_filtered = df_newest[['Amount', 'Naam (in database)']]

                        # Vergelijk de gegevens en categoriseer ze in drie secties
                        comparison_df = pd.merge(df_1_filtered, df_2_filtered, on='Naam (in database)', how='outer', suffixes=('_ref', '_later')).fillna(0)

                        comparison_df['Amount_ref'] = comparison_df['Amount_ref'].round(0).astype(int)
                        comparison_df['Amount_later'] = comparison_df['Amount_later'].round(0).astype(int)

                        sectie_1 = comparison_df[comparison_df['Amount_later'] == comparison_df['Amount_ref']]
                        sectie_2 = comparison_df[comparison_df['Amount_later'] > comparison_df['Amount_ref']]
                        sectie_3 = comparison_df[comparison_df['Amount_later'] < comparison_df['Amount_ref']]

                        # Zet de gegevens om naar lijsten voor de PDF
                        sectie_1_data = [["", int(min(row[0], row[2])), row[1], int(row[0]), int(row[2])] for row in sectie_1.values.tolist()]
                        sectie_2_data = [["", int(row[2] - row[0]), row[1], int(row[0]), int(row[2])] for row in sectie_2.values.tolist()]
                        sectie_3_data = [["", int(row[0] - row[2]), row[1], int(row[0]), int(row[2])] for row in sectie_3.values.tolist()]

                        # Genereer de PDF
                        pdf_buffer = create_pdf_with_correct_columns(sectie_1_data, sectie_2_data, sectie_3_data, projectnaam_oldest, projectnaam_newest)

                        # Downloadknop voor de PDF
                        st.download_button(
                            label="Download resultaten als PDF",
                            data=pdf_buffer,
                            file_name="overzicht_materialen.pdf",
                            mime="application/pdf"
                        )
                    else:
                        st.error("De vereiste kolommen 'Amount' en 'Naam (in database)' ontbreken in een van de CSV-bestanden.")
            except ValueError as e:
                st.error(f"Fout bij het verwerken van de datums: {e}")
        else:
            st.error("Bestandsnamen hebben niet het verwachte formaat: Type - Projectnaam - Datum")
else:
    st.write("Upload beide CSV-bestanden om door te gaan.")
