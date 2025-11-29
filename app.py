from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory, send_file

import os, random, string
from datetime import datetime
from fpdf import FPDF
import socket

# Configuración de carpetas antes de crear la app
UPLOAD_FOLDER = 'static/fotos'
DOCUMENT_FOLDER = 'static/documentos'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOCUMENT_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'supersecreto'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['DOCUMENT_FOLDER'] = DOCUMENT_FOLDER

import mysql.connector

# Conexión con XAMPP (MySQL local)
conn = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",  # Deja vacío si no pusiste contraseña en XAMPP
    database="uptecamac"
)
cursor = conn.cursor(dictionary=True)

registros = {}

ADMIN_USER = "admin"
ADMIN_PASS = "1234"


# Página principal
@app.route('/')
def index():
    return render_template('index.html')



# Convocatoria (muestra y registro)
@app.route('/convocatoria')
def convocatoria():
    registro_bloqueado = session.get('registro_bloqueado', False)
    registro_rechazado = session.get('registro_rechazado', False)
    return render_template('convocatoria.html', registro_bloqueado=registro_bloqueado, registro_rechazado=registro_rechazado)



@app.route('/registrar', methods=['POST'])
def registrar():
    curp = request.form['curp'].upper()
    curp_pdf = request.files.get('curp_pdf')
    acta_pdf = request.files.get('acta_pdf')

    if not curp_pdf or not acta_pdf:
        flash("❌ Debes subir ambos documentos PDF.")
        return redirect(url_for('convocatoria'))

    curp_filename = f"{curp}_curp.pdf"
    acta_filename = f"{curp}_acta.pdf"

    curp_path = os.path.join(app.config['DOCUMENT_FOLDER'], curp_filename)
    acta_path = os.path.join(app.config['DOCUMENT_FOLDER'], acta_filename)

    curp_pdf.save(curp_path)
    acta_pdf.save(acta_path)

    registros[curp] = {
        'nombre': request.form['nombre'],
        'apellidos': request.form['apellidos'],
        'curp': request.form["curp"],
        'rfc': request.form['rfc'],
        'nss': request.form['nss'],
        'telefono': request.form['telefono'],
        'correo': request.form['correo'],
        'sexo': request.form['sexo'],
        'matricula': None,
        'foto': None,
        'foto_validada': None,
        'fecha': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'curp_pdf': curp_filename,
        'acta_pdf': acta_filename
    }

    # Bloquear registro hasta validación admin
    session['registro_bloqueado'] = True
    session['registro_rechazado'] = False
    session['curp_registrado'] = curp

    flash("Su registro está en proceso de validación.")
    return redirect(url_for('convocatoria'))


# Validaciones (consulta)
@app.route('/validaciones')
def validaciones():
    resultado = session.pop('resultado_validacion', None)
    return render_template('validaciones.html', resultado=resultado)

@app.route('/validar', methods=['POST'])
def validar():
    curp = request.form['curp']
    correo = request.form['correo']
    user = registros.get(curp)
    if user and user['correo'] == correo:
        session['resultado_validacion'] = user  # Para mostrar los datos debajo del formulario
        if user['matricula']:
            flash(f"matricula:{user['matricula']}")
        elif user.get('registro_validado') is False:
            flash("❌ Tu registro fue rechazado. Corrige tus datos y vuelve a intentarlo.")
        else:
            flash("⏳ Tu registro aún no ha sido validado. Por favor espera la revisión del administrador.")
    else:
        session['resultado_validacion'] = None
        flash("❌ Los datos ingresados son incorrectos. Intenta de nuevo.")
    return redirect(url_for('validaciones'))


# Toma de foto
@app.route('/tomar_foto', methods=['GET', 'POST'])
def tomar_foto():
    if request.method == 'POST':
        curp = request.form.get('curp')
        matricula = request.form.get('matricula')
        foto = request.files.get('foto')

        if not curp or not matricula or not foto:
            flash("⚠️ CURP, matrícula o foto faltante.")
            return redirect(url_for('tomar_foto'))

        if curp not in registros:
            flash("❌ CURP no encontrado en registros.")
            return redirect(url_for('tomar_foto'))

        filename = f"{curp}.jpg"
        foto_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        foto.save(foto_path)

        registros[curp]['matricula'] = matricula
        registros[curp]['foto'] = filename
        registros[curp]['foto_validada'] = None

        flash("📸 Foto subida correctamente. Espera validación del administrador.")
        return redirect(url_for('tomar_foto'))

    return render_template('tomar_foto.html')

    




# Login administrador
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        if usuario == ADMIN_USER and password == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin'))
        else:
            flash('❌ Usuario o contraseña incorrectos.')
            return redirect(url_for('login'))
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash('🔒 Sesión cerrada.')
    return redirect(url_for('login'))


# Panel administrador
@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect(url_for('login'))
    return render_template('admin.html', registros=registros)


# Validación de datos

@app.route('/aprobar_registro', methods=['POST'])
def aprobar_registro():
    curp = request.form['curp']
    if curp in registros:
        registros[curp]['matricula'] = ''.join(random.choices(string.digits, k=8))
        flash(f'✅ Registro de {curp} aprobado. Matrícula asignada.')
        # Si el usuario está en sesión, desbloquear registro
        if session.get('curp_registrado') == curp:
            session['registro_bloqueado'] = False
            session['registro_rechazado'] = False
            session.pop('curp_registrado', None)
    return redirect(url_for('admin'))



@app.route('/rechazar_registro', methods=['POST'])
def rechazar_registro():
    curp = request.form['curp']
    if curp in registros:
        registros[curp]['matricula'] = None
        flash(f'❌ Registro de {curp} rechazado.')
        # Si el usuario está en sesión, permitir reintentar
        if session.get('curp_registrado') == curp:
            session['registro_bloqueado'] = False
            session['registro_rechazado'] = True
            session.pop('curp_registrado', None)
    return redirect(url_for('admin'))


# Validar foto
@app.route('/validar_foto', methods=['POST'])
def validar_foto():
    curp = request.form['curp']
    if curp in registros and registros[curp]['foto']:
        registros[curp]['foto_validada'] = True
        flash(f"✅ Foto de {curp} validada.")
    return redirect(url_for('admin'))


@app.route('/rechazar_foto', methods=['POST'])
def rechazar_foto():
    curp = request.form['curp']
    if curp in registros and registros[curp]['foto']:
        path = os.path.join(app.config['UPLOAD_FOLDER'], registros[curp]['foto'])
        if os.path.exists(path):
            os.remove(path)
        registros[curp]['foto'] = None
        registros[curp]['foto_validada'] = False
        flash(f"❌ Foto de {curp} rechazada y eliminada.")
    return redirect(url_for('admin'))


# Exportar PDF
@app.route('/exportar_pdf')
def exportar_pdf():
    if not session.get('admin'):
        return redirect(url_for('login'))

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Registros de Usuarios - Universidad Politécnica de Tecámac", ln=1, align='C')
    pdf.ln(10)

    for curp, datos in registros.items():
        pdf.cell(200, 10, txt=f"Nombre: {datos['nombre']} {datos['apellidos']}", ln=1)
        pdf.cell(200, 10, txt=f"CURP: {curp} | Matrícula: {datos['matricula'] or '---'}", ln=1)
        pdf.cell(200, 10, txt=f"Correo: {datos['correo']} | Fecha: {datos['fecha']}", ln=1)
        pdf.ln(5)

    pdf_path = "registros.pdf"
    pdf.output(pdf_path)
    return send_file(pdf_path, as_attachment=True)


@app.route('/fotos/<filename>')
def fotos(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
@app.route('/documentos/<filename>')
def documentos(filename):
    return send_from_directory(app.config['DOCUMENT_FOLDER'], filename)
    return render_template('tomar_foto.html', foto_bloqueada=True)


if __name__ == '__main__':

    app.run(host="0.0.0.0", port=5000,debug=True)
