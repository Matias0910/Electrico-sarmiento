from fpdf import FPDF
from fpdf.enums import XPos, YPos

class PDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Informe Técnico (Electrico) - Depósito Castelar', new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf(fecha, tren, km, tareas, observaciones):
    """Genera un PDF con diseño profesional y lo devuelve como bytes."""
    pdf = PDF()
    pdf.add_page()

    # --- Datos Generales ---
    trenes_argentinos_blue = (0, 115, 184)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_fill_color(*trenes_argentinos_blue)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, f"Informe del Tren {tren}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L', fill=True)
    pdf.set_text_color(0, 0, 0) # Restaurar color de texto a negro
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 8, text=f"Fecha: {fecha.strftime('%d/%m/%Y')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 8, text=f"Kilometraje: {km} km", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(10)

    # --- Tabla de Tareas ---
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(0, 10, "Tareas Realizadas", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')

    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(50, 50, 50) # Gris oscuro
    pdf.set_text_color(255, 255, 255)
    pdf.cell(pdf.epw, 8, "Tareas", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(0, 0, 0)
    for item in tareas:
        sistema = item['sistema']
        datos_legibles = " | ".join([f"{k}: {v}" for k, v in item['datos'].items()])
        texto_linea = f"- {sistema}: {datos_legibles}"
        pdf.multi_cell(pdf.epw, 8, txt=texto_linea, border="LR", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='L')
    pdf.cell(pdf.epw, 0, '', 'T', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    if observaciones:
        pdf.ln(10)
        pdf.set_font("Helvetica", 'B', 12)
        pdf.cell(0, 10, "Observaciones", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(pdf.epw, 8, text=observaciones, border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())