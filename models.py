from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    nombre = db.Column(db.String(100))
    matricula = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def get_id(self):
        return str(self.id)


class Expediente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    categoria = db.Column(db.String(50))
    caratula = db.Column(db.String(500))
    responsable = db.Column(db.String(20))
    estado = db.Column(db.String(30), default='ACTIVO')
    notas = db.Column(db.Text)
    tipo_honorario = db.Column(db.String(30))
    monto_pactado = db.Column(db.Float)
    porcentaje_cuota = db.Column(db.Float)
    creado = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tareas = db.relationship('Tarea', backref='expediente', lazy=True,
                             cascade='all, delete-orphan',
                             order_by='Tarea.vencimiento')
    honorarios = db.relationship('Honorario', backref='expediente', lazy=True,
                                 cascade='all, delete-orphan')
    recibos = db.relationship('Recibo', backref='expediente', lazy=True,
                              cascade='all, delete-orphan',
                              order_by='Recibo.creado.desc()')

    @property
    def total_cobrado(self):
        return sum(r.monto or 0 for r in self.recibos if r.estado == 'Cobrado')

    @property
    def pendiente_cobrar(self):
        return (self.monto_pactado or 0) - self.total_cobrado

    @property
    def tareas_pendientes(self):
        return [t for t in self.tareas if t.estado in ('PENDIENTE', 'EN PROCESO')]


class Tarea(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo_tarea = db.Column(db.String(20))
    expediente_id = db.Column(db.Integer, db.ForeignKey('expediente.id'), nullable=False)
    tipo = db.Column(db.String(30))
    descripcion = db.Column(db.Text)
    fecha = db.Column(db.String(20))
    vencimiento = db.Column(db.String(20))
    responsable = db.Column(db.String(20))
    estado = db.Column(db.String(20), default='PENDIENTE')
    creado = db.Column(db.DateTime, default=datetime.utcnow)


class Honorario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expediente_id = db.Column(db.Integer, db.ForeignKey('expediente.id'), nullable=False)
    tipo = db.Column(db.String(30))
    porcentaje = db.Column(db.Float)
    monto = db.Column(db.Float)
    fecha_pacto = db.Column(db.String(20))
    abogado = db.Column(db.String(50))
    notas = db.Column(db.Text)
    creado = db.Column(db.DateTime, default=datetime.utcnow)


class Recibo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20))
    expediente_id = db.Column(db.Integer, db.ForeignKey('expediente.id'), nullable=False)
    fecha = db.Column(db.String(20))
    monto = db.Column(db.Float)
    concepto = db.Column(db.Text)
    forma_pago = db.Column(db.String(30))
    estado = db.Column(db.String(20), default='Emitido')
    creado = db.Column(db.DateTime, default=datetime.utcnow)
