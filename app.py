import os
from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Expediente, Tarea, Honorario, Recibo
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'estudio-molina-clave-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///estudio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Ingresá para acceder al sistema.'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Constantes ────────────────────────────────────────────────────────────────
CATEGORIAS  = ['LABORAL', 'CIVIL', 'FAMILIA', 'PENAL', 'COMERCIAL', 'OTRO']
ESTADOS_EXP = ['ACTIVO', 'PARA INICIAR', 'EN ESPERA', 'PENDIENTE TAREA', 'FINALIZADO', 'ARCHIVO']
TIPOS_HON   = ['Cuota Litis', 'Honorarios Fijos', 'Cuotas Periodicas', 'Judicial', 'Sin pacto']
TIPOS_TAREA = ['AUDIENCIA', 'ESCRITO', 'NOTIFICACION', 'OTRO']
ESTADOS_TAR = ['PENDIENTE', 'EN PROCESO', 'COMPLETADA', 'CANCELADA']
FORMAS_PAGO = ['Efectivo', 'Transferencia', 'Cheque']
ESTADOS_REC = ['Emitido', 'Cobrado', 'Anulado']
RESPONSABLES = ['MIO', 'MOLINA', 'SALAS', 'COMPARTIDO']


# ── Helpers ───────────────────────────────────────────────────────────────────
def next_codigo(categoria):
    prefix = categoria[:3].upper()
    count = Expediente.query.filter(
        Expediente.codigo.like(prefix + '-%')
    ).count()
    return '{}-{}'.format(prefix, str(count + 1).zfill(3))


def next_tarea_codigo():
    count = Tarea.query.count()
    return 'T-{}'.format(str(count + 1).zfill(4))


def next_recibo_numero():
    count = Recibo.query.count()
    return 'R-{}'.format(str(count + 1).zfill(4))


# ── Inicializar DB y usuarios por defecto ─────────────────────────────────────
def init_db():
    db.create_all()
    if not User.query.filter_by(username='molina').first():
        u = User(username='molina', nombre='Dr. Raúl Javier Molina', matricula='5271')
        u.set_password('molina1234')
        db.session.add(u)
    if not User.query.filter_by(username='salas').first():
        u = User(username='salas', nombre='Dr. Agustín Gabriel Salas', matricula='7093')
        u.set_password('salas1234')
        db.session.add(u)
    db.session.commit()


with app.app_context():
    init_db()


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            return redirect(request.args.get('next') or url_for('dashboard'))
        flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def dashboard():
    activos = Expediente.query.filter(
        Expediente.estado.in_(['ACTIVO', 'EN ESPERA', 'PENDIENTE TAREA', 'PARA INICIAR'])
    ).count()
    total_exp = Expediente.query.count()
    tareas_pendientes = Tarea.query.filter(
        Tarea.estado.in_(['PENDIENTE', 'EN PROCESO'])
    ).order_by(Tarea.vencimiento).limit(12).all()
    recibos_recientes = Recibo.query.order_by(Recibo.creado.desc()).limit(6).all()
    total_cobrado = db.session.query(
        db.func.sum(Recibo.monto)
    ).filter(Recibo.estado == 'Cobrado').scalar() or 0
    total_pactado = db.session.query(
        db.func.sum(Expediente.monto_pactado)
    ).scalar() or 0
    by_cat = db.session.query(
        Expediente.categoria, db.func.count(Expediente.id)
    ).group_by(Expediente.categoria).all()
    return render_template('dashboard.html',
        activos=activos, total_exp=total_exp,
        tareas_pendientes=tareas_pendientes,
        recibos_recientes=recibos_recientes,
        total_cobrado=total_cobrado, total_pactado=total_pactado,
        by_cat=by_cat)


# ── Expedientes ───────────────────────────────────────────────────────────────
@app.route('/expedientes')
@login_required
def expedientes_list():
    q   = request.args.get('q', '').strip()
    cat = request.args.get('cat', '')
    est = request.args.get('est', '')
    query = Expediente.query
    if q:
        query = query.filter(
            db.or_(
                Expediente.caratula.ilike('%' + q + '%'),
                Expediente.codigo.ilike('%' + q + '%')
            )
        )
    if cat:
        query = query.filter_by(categoria=cat)
    if est:
        query = query.filter_by(estado=est)
    exps = query.order_by(Expediente.categoria, Expediente.codigo).all()
    return render_template('expedientes/list.html',
        expedientes=exps, q=q, cat=cat, est=est,
        categorias=CATEGORIAS, estados=ESTADOS_EXP)


@app.route('/expedientes/nuevo', methods=['GET', 'POST'])
@login_required
def expediente_nuevo():
    if request.method == 'POST':
        cat = request.form['categoria'].upper()
        mp  = request.form.get('monto_pactado', '').strip()
        pc  = request.form.get('porcentaje_cuota', '').strip()
        exp = Expediente(
            codigo=next_codigo(cat),
            categoria=cat,
            caratula=request.form['caratula'],
            responsable=request.form['responsable'],
            estado=request.form['estado'],
            notas=request.form.get('notas', ''),
            tipo_honorario=request.form.get('tipo_honorario', ''),
            monto_pactado=float(mp) if mp else None,
            porcentaje_cuota=float(pc) if pc else None,
        )
        db.session.add(exp)
        db.session.commit()
        flash('Expediente {} creado.'.format(exp.codigo), 'success')
        return redirect(url_for('expediente_detail', id=exp.id))
    return render_template('expedientes/form.html',
        exp=None, categorias=CATEGORIAS, estados=ESTADOS_EXP,
        tipos_hon=TIPOS_HON, responsables=RESPONSABLES, action='Nuevo')


@app.route('/expedientes/<int:id>')
@login_required
def expediente_detail(id):
    exp = Expediente.query.get_or_404(id)
    return render_template('expedientes/detail.html',
        exp=exp, tipos_tarea=TIPOS_TAREA, estados_tarea=ESTADOS_TAR,
        formas_pago=FORMAS_PAGO, estados_recibo=ESTADOS_REC,
        tipos_hon=TIPOS_HON, responsables=RESPONSABLES)


@app.route('/expedientes/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def expediente_editar(id):
    exp = Expediente.query.get_or_404(id)
    if request.method == 'POST':
        mp = request.form.get('monto_pactado', '').strip()
        pc = request.form.get('porcentaje_cuota', '').strip()
        exp.categoria      = request.form['categoria'].upper()
        exp.caratula       = request.form['caratula']
        exp.responsable    = request.form['responsable']
        exp.estado         = request.form['estado']
        exp.notas          = request.form.get('notas', '')
        exp.tipo_honorario = request.form.get('tipo_honorario', '')
        exp.monto_pactado  = float(mp) if mp else None
        exp.porcentaje_cuota = float(pc) if pc else None
        exp.actualizado    = datetime.utcnow()
        db.session.commit()
        flash('Expediente actualizado.', 'success')
        return redirect(url_for('expediente_detail', id=exp.id))
    return render_template('expedientes/form.html',
        exp=exp, categorias=CATEGORIAS, estados=ESTADOS_EXP,
        tipos_hon=TIPOS_HON, responsables=RESPONSABLES, action='Editar')


@app.route('/expedientes/<int:id>/eliminar', methods=['POST'])
@login_required
def expediente_eliminar(id):
    exp = Expediente.query.get_or_404(id)
    codigo = exp.codigo
    db.session.delete(exp)
    db.session.commit()
    flash('Expediente {} eliminado.'.format(codigo), 'info')
    return redirect(url_for('expedientes_list'))


# ── Tareas ────────────────────────────────────────────────────────────────────
@app.route('/tareas')
@login_required
def tareas_list():
    est  = request.args.get('est', '')
    resp = request.args.get('resp', '')
    query = Tarea.query
    if est:
        query = query.filter_by(estado=est)
    if resp:
        query = query.filter_by(responsable=resp)
    tareas = query.order_by(Tarea.vencimiento, Tarea.creado).all()
    return render_template('tareas/list.html',
        tareas=tareas, estados=ESTADOS_TAR,
        responsables=RESPONSABLES, est=est, resp=resp)


@app.route('/tareas/nueva', methods=['GET', 'POST'])
@login_required
def tarea_nueva():
    exp_id = request.args.get('exp_id')
    if request.method == 'POST':
        eid = request.form.get('expediente_id')
        t = Tarea(
            codigo_tarea=next_tarea_codigo(),
            expediente_id=int(eid),
            tipo=request.form['tipo'],
            descripcion=request.form['descripcion'],
            fecha=request.form.get('fecha', ''),
            vencimiento=request.form.get('vencimiento', ''),
            responsable=request.form['responsable'],
            estado=request.form['estado'],
        )
        db.session.add(t)
        db.session.commit()
        flash('Tarea {} creada.'.format(t.codigo_tarea), 'success')
        return redirect(url_for('expediente_detail', id=eid))
    expedientes = Expediente.query.order_by(Expediente.codigo).all()
    return render_template('tareas/form.html',
        tarea=None, expedientes=expedientes, tipos=TIPOS_TAREA,
        estados=ESTADOS_TAR, responsables=RESPONSABLES,
        exp_id=exp_id, action='Nueva')


@app.route('/tareas/<int:id>/editar', methods=['GET', 'POST'])
@login_required
def tarea_editar(id):
    t = Tarea.query.get_or_404(id)
    if request.method == 'POST':
        t.tipo        = request.form['tipo']
        t.descripcion = request.form['descripcion']
        t.fecha       = request.form.get('fecha', '')
        t.vencimiento = request.form.get('vencimiento', '')
        t.responsable = request.form['responsable']
        t.estado      = request.form['estado']
        db.session.commit()
        flash('Tarea actualizada.', 'success')
        return redirect(url_for('expediente_detail', id=t.expediente_id))
    expedientes = Expediente.query.order_by(Expediente.codigo).all()
    return render_template('tareas/form.html',
        tarea=t, expedientes=expedientes, tipos=TIPOS_TAREA,
        estados=ESTADOS_TAR, responsables=RESPONSABLES,
        exp_id=t.expediente_id, action='Editar')


@app.route('/tareas/<int:id>/estado', methods=['POST'])
@login_required
def tarea_estado(id):
    t = Tarea.query.get_or_404(id)
    t.estado = request.form['estado']
    db.session.commit()
    return redirect(request.referrer or url_for('tareas_list'))


@app.route('/tareas/<int:id>/eliminar', methods=['POST'])
@login_required
def tarea_eliminar(id):
    t = Tarea.query.get_or_404(id)
    eid = t.expediente_id
    db.session.delete(t)
    db.session.commit()
    flash('Tarea eliminada.', 'info')
    return redirect(url_for('expediente_detail', id=eid))


# ── Honorarios ────────────────────────────────────────────────────────────────
@app.route('/honorarios')
@login_required
def honorarios_list():
    honorarios = Honorario.query.order_by(Honorario.creado.desc()).all()
    recibos = Recibo.query.order_by(Recibo.creado.desc()).all()
    total_pactado = db.session.query(db.func.sum(Honorario.monto)).scalar() or 0
    total_cobrado = db.session.query(db.func.sum(Recibo.monto)).filter(
        Recibo.estado == 'Cobrado').scalar() or 0
    return render_template('honorarios/list.html',
        honorarios=honorarios, recibos=recibos,
        total_pactado=total_pactado, total_cobrado=total_cobrado)


@app.route('/honorarios/nuevo', methods=['GET', 'POST'])
@login_required
def honorario_nuevo():
    exp_id = request.args.get('exp_id')
    if request.method == 'POST':
        eid   = request.form.get('expediente_id')
        monto = request.form.get('monto', '').strip()
        porc  = request.form.get('porcentaje', '').strip()
        h = Honorario(
            expediente_id=int(eid),
            tipo=request.form['tipo'],
            porcentaje=float(porc) if porc else None,
            monto=float(monto) if monto else None,
            fecha_pacto=request.form.get('fecha_pacto', ''),
            abogado=request.form['abogado'],
            notas=request.form.get('notas', ''),
        )
        db.session.add(h)
        exp = Expediente.query.get(int(eid))
        if exp and h.monto:
            exp.monto_pactado  = h.monto
            exp.tipo_honorario = h.tipo
        db.session.commit()
        flash('Pacto de honorarios registrado.', 'success')
        return redirect(url_for('expediente_detail', id=eid))
    expedientes = Expediente.query.order_by(Expediente.codigo).all()
    return render_template('honorarios/form.html',
        expedientes=expedientes, tipos=TIPOS_HON,
        responsables=RESPONSABLES, exp_id=exp_id)


# ── Recibos ───────────────────────────────────────────────────────────────────
@app.route('/recibos/nuevo', methods=['GET', 'POST'])
@login_required
def recibo_nuevo():
    exp_id = request.args.get('exp_id')
    if request.method == 'POST':
        eid   = request.form.get('expediente_id')
        monto = request.form.get('monto', '').strip()
        r = Recibo(
            numero=next_recibo_numero(),
            expediente_id=int(eid),
            fecha=request.form.get('fecha', ''),
            monto=float(monto) if monto else None,
            concepto=request.form.get('concepto', ''),
            forma_pago=request.form['forma_pago'],
            estado=request.form['estado'],
        )
        db.session.add(r)
        db.session.commit()
        flash('Recibo {} registrado.'.format(r.numero), 'success')
        return redirect(url_for('expediente_detail', id=eid))
    expedientes = Expediente.query.order_by(Expediente.codigo).all()
    return render_template('honorarios/recibo_form.html',
        expedientes=expedientes, formas_pago=FORMAS_PAGO,
        estados=ESTADOS_REC, exp_id=exp_id)


@app.route('/recibos/<int:id>/estado', methods=['POST'])
@login_required
def recibo_estado(id):
    r = Recibo.query.get_or_404(id)
    r.estado = request.form['estado']
    db.session.commit()
    return redirect(request.referrer or url_for('honorarios_list'))


@app.route('/recibos/<int:id>/eliminar', methods=['POST'])
@login_required
def recibo_eliminar(id):
    r = Recibo.query.get_or_404(id)
    eid = r.expediente_id
    db.session.delete(r)
    db.session.commit()
    flash('Recibo eliminado.', 'info')
    return redirect(url_for('expediente_detail', id=eid))


# ── Cambiar contraseña ────────────────────────────────────────────────────────
@app.route('/perfil', methods=['GET', 'POST'])
@login_required
def perfil():
    if request.method == 'POST':
        actual = request.form.get('actual', '')
        nueva  = request.form.get('nueva', '')
        if not current_user.check_password(actual):
            flash('La contraseña actual es incorrecta.', 'danger')
        elif len(nueva) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres.', 'warning')
        else:
            current_user.set_password(nueva)
            db.session.commit()
            flash('Contraseña actualizada correctamente.', 'success')
    return render_template('perfil.html')


# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/expediente/<int:id>')
@login_required
def api_expediente(id):
    exp = Expediente.query.get_or_404(id)
    return jsonify({'caratula': exp.caratula, 'codigo': exp.codigo})


if __name__ == '__main__':
    app.run(debug=False)
