from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy() # Sera initialisé dans app.py

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Temps en minutes par semaine
    weekly_minutes = db.Column(db.Integer, nullable=False)
    # Catégories possibles
    category = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'weekly_minutes': self.weekly_minutes,
            'category': self.category
        }

# Optionnel : Pour stocker des paramètres comme l'URL du calendrier si on ne veut pas utiliser .env
# class Setting(db.Model):
#     key = db.Column(db.String(50), primary_key=True)
#     value = db.Column(db.String(255))