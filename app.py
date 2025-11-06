import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from docxtpl import DocxTemplate
from io import BytesIO
import locale
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia-dapur-bni-1946'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///debitur.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

TEMPLATE_FILENAME = "template_kredit.docx"
ALLOWED_EXTENSIONS = {'docx'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Daftar Key untuk pemformatan
DATE_KEYS = [
    'tgl_lahir_pemohon', 'tgl_terbit_ktp', 'tgl_mulai_kerja',
    'tgl_sk_cpns', 'tgl_sk_golongan', 'tgl_pensiun_pemohon',
    'tgl_slik', 'mitigasi_slik_tgl_surat', 'tgl_call_memo'
]

# (PERUBAHAN: Diperpanjang sampai 15)
NOMINAL_KEYS = [
    'plafon_kredit_dimohon', 'usulan_plafon_kredit',
    'gaji_bulan_1_jumlah', 'gaji_bulan_2_jumlah', 'gaji_bulan_3_jumlah',
    'estimasi_hak_pensiun', 'taspen_tht', 'taspen_hak_pensiun',
    'biaya_provisi_nominal', 'biaya_tata_laksana_nominal',
    'info_gaji_bendahara', 
    'slik_bank_1_maks', 'slik_bank_1_outs',
    'slik_bank_2_maks', 'slik_bank_2_outs', 
    'slik_bank_3_maks', 'slik_bank_3_outs',
    'slik_bank_4_maks', 'slik_bank_4_outs', 
    'slik_bank_5_maks', 'slik_bank_5_outs',
    'slik_bank_6_maks', 'slik_bank_6_outs', 
    'slik_bank_7_maks', 'slik_bank_7_outs',
    'slik_bank_8_maks', 'slik_bank_8_outs', 
    'slik_bank_9_maks', 'slik_bank_9_outs',
    'slik_bank_10_maks', 'slik_bank_10_outs',
    'slik_bank_11_maks', 'slik_bank_11_outs', # BARU
    'slik_bank_12_maks', 'slik_bank_12_outs', # BARU
    'slik_bank_13_maks', 'slik_bank_13_outs', # BARU
    'slik_bank_14_maks', 'slik_bank_14_outs', # BARU
    'slik_bank_15_maks', 'slik_bank_15_outs', # BARU
]

# --- MODEL DATABASE ---
class Debitur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama_pemohon = db.Column(db.String(100), nullable=False)
    no_ktp = db.Column(db.String(20), nullable=False)
    tanggal_input = db.Column(db.DateTime, default=datetime.utcnow)
    data_lengkap = db.Column(db.Text, nullable=False)

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html', data={})

@app.route('/riwayat')
def riwayat():
    search_query = request.args.get('q', '')
    query = Debitur.query
    if search_query:
        search_term = f"%{search_query}%"
        query = query.filter(
            or_(
                Debitur.nama_pemohon.ilike(search_term),
                Debitur.no_ktp.ilike(search_term)
            )
        )
    all_debitur = query.order_by(Debitur.tanggal_input.desc()).all()
    return render_template('riwayat.html', 
                           debitur_list=all_debitur, 
                           search_query=search_query)

@app.route('/edit/<int:id>')
def edit(id):
    debitur = Debitur.query.get_or_404(id)
    data = json.loads(debitur.data_lengkap)
    return render_template('index.html', data=data, debitur_id=debitur.id)

@app.route('/simpan', methods=['POST'])
def simpan():
    form_data = request.form.to_dict()
    debitur_id = form_data.pop('debitur_id', None)

    try:
        # Bersihkan nominal
        for key in NOMINAL_KEYS:
            if key in form_data:
                form_data[key] = form_data[key].replace('.', '')

        if debitur_id and debitur_id.isdigit():
            # --- MODE UPDATE ---
            debitur = Debitur.query.get_or_404(int(debitur_id))
            debitur.nama_pemohon = form_data.get('nama_pemohon', 'Tanpa Nama')
            debitur.no_ktp = form_data.get('no_ktp_pemohon', '000')
            debitur.data_lengkap = json.dumps(form_data)
        else:
            # --- MODE CREATE ---
            new_debitur = Debitur(
                nama_pemohon=form_data.get('nama_pemohon', 'Tanpa Nama'),
                no_ktp=form_data.get('no_ktp_pemohon', '000'),
                data_lengkap=json.dumps(form_data)
            )
            db.session.add(new_debitur)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return f"Terjadi error saat menyimpan data: {e}", 500
    return redirect(url_for('riwayat'))

@app.route('/generate/<int:id>')
def generate_docx(id):
    debitur = Debitur.query.get_or_404(id)
    context = json.loads(debitur.data_lengkap)
    
    # Atur Locale (HANYA UNTUK TANGGAL)
    try:
        locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Indonesian')
        except locale.Error:
            locale.setlocale(locale.LC_ALL, '') 
            
    # Format Tanggal
    for key in DATE_KEYS:
        if key in context and context[key]:
            try:
                date_obj = datetime.strptime(context[key], '%Y-%m-%d')
                context[key] = date_obj.strftime('%d %B %Y')
            except ValueError: pass
    
    # Format Nominal (Rupiah)
    for key in NOMINAL_KEYS:
        if key in context and context[key]:
            try:
                nilai_angka = int(context[key])
                context[key] = f"{nilai_angka:,}".replace(',', '.')
            except (ValueError, TypeError):
                pass
    
    template_path = os.path.join(app.root_path, TEMPLATE_FILENAME)
    
    if not os.path.exists(template_path):
        return f"Error: File template {TEMPLATE_FILENAME} tidak ditemukan!", 404

    doc = DocxTemplate(template_path)
    
    try:
        doc.render(context)
    except Exception as e:
        return f"Error saat render template: {e}.", 500

    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    
    filename = f"Kredit_{context.get('nama_pemohon', 'Debitur')}_{context.get('no_ktp_pemohon', 'NIK')}.docx"
    return send_file(file_stream, as_attachment=True, download_name=filename)

@app.route('/hapus/<int:id>')
def hapus(id):
    debitur = Debitur.query.get_or_404(id)
    db.session.delete(debitur)
    db.session.commit()
    flash('Data debitur berhasil dihapus.', 'success')
    return redirect(url_for('riwayat'))

# --- RUTE UNTUK KELOLA TEMPLATE ---

@app.route('/admin')
def admin():
    """Menampilkan halaman upload template."""
    return render_template('admin.html')

@app.route('/upload_template', methods=['POST'])
def upload_template():
    """Memproses file template yang di-upload."""
    if 'file' not in request.files:
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('admin'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('Tidak ada file yang dipilih.', 'danger')
        return redirect(url_for('admin'))
    
    if file and allowed_file(file.filename):
        filename = secure_filename(TEMPLATE_FILENAME)
        save_path = os.path.join(app.root_path, filename)
        
        try:
            file.save(save_path)
            flash(f'Template "{filename}" berhasil diperbarui.', 'success')
        except Exception as e:
            flash(f'Terjadi error saat menyimpan file: {e}', 'danger')
            
    else:
        flash('Format file tidak diizinkan. Harap upload file .docx', 'danger')
        
    return redirect(url_for('admin'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)