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
import webbrowser
from threading import Timer
import math # (BARU) Diperlukan untuk kalkulasi angsuran

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

# (PERBAIKAN) Menambahkan key angsuran baru
NOMINAL_KEYS = [
    'plafon_kredit_dimohon', 'usulan_plafon_kredit', 'usulan_angsuran', # 'usulan_angsuran' BARU
    'gaji_bulan_1_jumlah', 'gaji_bulan_2_jumlah', 'gaji_bulan_3_jumlah',
    'estimasi_hak_pensiun', 'taspen_tht', 'taspen_hak_pensiun',
    'biaya_provisi_nominal', 'biaya_tata_laksana_nominal',
    'info_gaji_bendahara', 
    'slik_bank_1_maks', 'slik_bank_1_outs', 'slik_bank_1_angsuran', # BARU
    'slik_bank_2_maks', 'slik_bank_2_outs', 'slik_bank_2_angsuran', # BARU
    'slik_bank_3_maks', 'slik_bank_3_outs', 'slik_bank_3_angsuran', # BARU
    'slik_bank_4_maks', 'slik_bank_4_outs', 'slik_bank_4_angsuran', # BARU
    'slik_bank_5_maks', 'slik_bank_5_outs', 'slik_bank_5_angsuran', # BARU
    'slik_bank_6_maks', 'slik_bank_6_outs', 'slik_bank_6_angsuran', # BARU
    'slik_bank_7_maks', 'slik_bank_7_outs', 'slik_bank_7_angsuran', # BARU
    'slik_bank_8_maks', 'slik_bank_8_outs', 'slik_bank_8_angsuran', # BARU
    'slik_bank_9_maks', 'slik_bank_9_outs', 'slik_bank_9_angsuran', # BARU
    'slik_bank_10_maks', 'slik_bank_10_outs', 'slik_bank_10_angsuran', # BARU
    'slik_bank_11_maks', 'slik_bank_11_outs', 'slik_bank_11_angsuran', # BARU
    'slik_bank_12_maks', 'slik_bank_12_outs', 'slik_bank_12_angsuran', # BARU
    'slik_bank_13_maks', 'slik_bank_13_outs', 'slik_bank_13_angsuran', # BARU
    'slik_bank_14_maks', 'slik_bank_14_outs', 'slik_bank_14_angsuran', # BARU
    'slik_bank_15_maks', 'slik_bank_15_outs', 'slik_bank_15_angsuran', # BARU
]

# (BARU) Fungsi kalkulasi angsuran (PMT)
def calculate_pmt(principal, annual_rate_percent, months):
    try:
        principal = float(principal)
        annual_rate_percent = float(annual_rate_percent)
        months = int(months)
        
        if annual_rate_percent == 0:
            return principal / months if months > 0 else 0
        
        monthly_rate = (annual_rate_percent / 100) / 12
        if months == 0:
            return 0
        
        pmt = principal * (monthly_rate * (1 + monthly_rate) ** months) / ((1 + monthly_rate) ** months - 1)
        return math.ceil(pmt) # Pembulatan ke atas
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

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
            debitur = Debitur.query.get_or_404(int(debitur_id))
            debitur.nama_pemohon = form_data.get('nama_pemohon', 'Tanpa Nama')
            debitur.no_ktp = form_data.get('no_ktp_pemohon', '000')
            debitur.data_lengkap = json.dumps(form_data)
        else:
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
    
    # Atur Locale
    try:
        locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'Indonesian')
        except locale.Error:
            locale.setlocale(locale.LC_ALL, '') 
            
    # --- (BARU) BLOK KALKULASI RPC & DSR ---
    try:
        # 1. Hitung Angsuran Baru (Usulan)
        plafon = context.get('usulan_plafon_kredit', '0').replace('.', '')
        tenor = context.get('usulan_jangka_waktu_bulan', '0')
        bunga = context.get('usulan_bunga_persen', '0')
        
        # Kalkulasi PMT (Payment)
        usulan_angsuran = calculate_pmt(plafon, bunga, tenor)
        context['usulan_angsuran'] = usulan_angsuran # Simpan untuk docx

        # 2. Hitung Total Angsuran Eksisting
        total_angsuran_eksisting = 0
        if context.get('fasilitas_nihil') != 'ya':
            for i in range(1, 16):
                key = f'slik_bank_{i}_angsuran'
                angsuran_str = context.get(key, '0').replace('.', '')
                total_angsuran_eksisting += int(angsuran_str) if angsuran_str.isdigit() else 0
        
        # 3. Hitung RPC
        penghasilan_str = context.get('estimasi_hak_pensiun', '0').replace('.', '')
        penghasilan = int(penghasilan_str) if penghasilan_str.isdigit() else 0
        
        dsc_90_nominal = penghasilan * 0.9
        maksimal_angsuran = dsc_90_nominal - total_angsuran_eksisting
        total_angsuran_baru = total_angsuran_eksisting + usulan_angsuran
        
        dsr = 0
        if penghasilan > 0:
            dsr = (total_angsuran_baru / penghasilan) * 100
        
        # 4. Masukkan hasil kalkulasi ke context
        context['rpc_penghasilan'] = penghasilan
        context['rpc_dsc_90'] = dsc_90_nominal
        context['rpc_total_angsuran_eksisting'] = total_angsuran_eksisting
        context['rpc_maksimal_angsuran'] = maksimal_angsuran
        context['rpc_total_angsuran_baru'] = total_angsuran_baru
        context['rpc_dsr'] = f"{dsr:.2f}" # Format 2 desimal

    except Exception as e:
        # Gagal kalkulasi, set nilai default agar tidak crash
        context['rpc_dsr'] = "Error"
        print(f"Error saat kalkulasi RPC: {e}")
    # --- AKHIR BLOK KALKULASI ---

    # Format Tanggal
    for key in DATE_KEYS:
        if key in context and context[key]:
            try:
                date_obj = datetime.strptime(context[key], '%Y-%m-%d')
                context[key] = date_obj.strftime('%d %B %Y')
            except ValueError: pass
    
    # Format Nominal (Rupiah)
    # Tambahkan key RPC ke daftar format
    rpc_keys_to_format = [
        'rpc_penghasilan', 'rpc_dsc_90', 'rpc_total_angsuran_eksisting',
        'rpc_maksimal_angsuran', 'rpc_total_angsuran_baru'
        # 'usulan_angsuran' sudah ada di NOMINAL_KEYS
    ]
    
    for key in NOMINAL_KEYS + rpc_keys_to_format:
        if key in context and context[key]:
            try:
                # Cek jika sudah diformat (seperti '87.73')
                if isinstance(context[key], str) and '.' in context[key]:
                     nilai_angka = int(float(context[key])) # handle 87.73 -> 87
                else:
                     nilai_angka = int(context[key])
                
                # Format ke '1.000.000'
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
    return render_template('admin.html')

@app.route('/upload_template', methods=['POST'])
def upload_template():
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

# --- FUNGSI UNTUK BUKA BROWSER ---
def open_browser():
      webbrowser.open_new('http://127.0.0.1:5000/')

if __name__ == '__main__':
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        Timer(1, open_browser).start()
    
    app.run(debug=True)