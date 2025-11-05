import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from docxtpl import DocxTemplate
from io import BytesIO
import locale

app = Flask(__name__)
app.config['SECRET_KEY'] = 'rahasia-dapur-bni-1946'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///debitur.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Daftar Key untuk pemformatan
DATE_KEYS = [
    'tgl_lahir_pemohon', 'tgl_terbit_ktp', 'tgl_mulai_kerja',
    'tgl_sk_cpns', 'tgl_sk_golongan', 'tgl_pensiun_pemohon',
    'tgl_slik', 'mitigasi_slik_tgl_surat', 'tgl_call_memo'
]

# (BARU) Daftar semua key field yang berisi nominal (Rupiah)
NOMINAL_KEYS = [
    'plafon_kredit_dimohon', 'usulan_plafon_kredit',
    'slik_bank_1_maks', 'slik_bank_1_outs',
    'gaji_bulan_1_jumlah', 'gaji_bulan_2_jumlah', 'gaji_bulan_3_jumlah',
    'estimasi_hak_pensiun', 'taspen_tht', 'taspen_hak_pensiun',
    'biaya_provisi_nominal', 'biaya_tata_laksana_nominal',
    # Catatan: 'blokir_angsuran_...' tidak termasuk karena itu 'kali', bukan Rupiah
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
        # --- (BARU) Blok Pembersihan Nominal ---
        # Kita harus membersihkan separator (misal '1.000.000' -> '1000000')
        # sebelum menyimpannya ke database
        for key in NOMINAL_KEYS:
            if key in form_data:
                # Menghapus titik (separator ribuan)
                form_data[key] = form_data[key].replace('.', '')
        # --- Akhir Blok Pembersihan ---

        if debitur_id and debitur_id.isdigit():
            # --- MODE UPDATE ---
            debitur = Debitur.query.get_or_404(int(debitur_id))
            debitur.nama_pemohon = form_data.get('nama_pemohon', 'Tanpa Nama')
            debitur.no_ktp = form_data.get('no_ktp_pemohon', '000')
            debitur.data_lengkap = json.dumps(form_data) # Simpan data yang sudah bersih
        else:
            # --- MODE CREATE ---
            new_debitur = Debitur(
                nama_pemohon=form_data.get('nama_pemohon', 'Tanpa Nama'),
                no_ktp=form_data.get('no_ktp_pemohon', '000'),
                data_lengkap=json.dumps(form_data) # Simpan data yang sudah bersih
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
    
    # --- Atur Locale ke Indonesia ---
    try:
        locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Indonesian')
        except locale.Error:
            locale.setlocale(locale.LC_ALL, '') # Fallback
            
    # --- Format Tanggal ---
    for key in DATE_KEYS:
        if key in context and context[key]:
            try:
                date_obj = datetime.strptime(context[key], '%Y-%m-%d')
                context[key] = date_obj.strftime('%d %B %Y')
            except ValueError:
                pass
    
    # --- (BARU) Format Nominal (Rupiah) ---
    for key in NOMINAL_KEYS:
        if key in context and context[key]:
            try:
                # 1. Ubah string angka (misal '1000000') menjadi angka
                nilai_angka = float(context[key])
                # 2. Format angka tsb menggunakan locale (menjadi '1.000.000')
                # :n menggunakan format angka dari locale, .0f Hapus desimal
                context[key] = f"{nilai_angka:n}" 
            except ValueError:
                # Jika data tidak valid, biarkan apa adanya
                pass
    # --- Akhir Blok Format Nominal ---
    
    template_path = "template_kredit.docx"
    if not os.path.exists(template_path):
        return "Error: File template_kredit.docx tidak ditemukan!", 404

    doc = DocxTemplate(template_path)
    
    try:
        doc.render(context)
    except Exception as e:
        return f"Error saat render template: {e}. Pastikan template menggunakan {{{{ variabel }}}} ganda.", 500

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
    return redirect(url_for('riwayat'))

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)