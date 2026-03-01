import sqlite3
import os

SECRET_PASSWORD = os.getenv('SECRET_PASSWORD')  # Substitua pela senha correta

class UserDatabaseManager:
    def __init__(self, db_name="levels.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        try:
            # Criamos a tabela se não existir
            self.cursor.execute('''
              CREATE TABLE IF NOT EXISTS users (
                  user_id INTEGER PRIMARY KEY,
                  xp INTEGER DEFAULT 0,
                  level INTEGER DEFAULT 1
              )
          ''')
            self.conn.commit()
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS checkins (
                    user_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    answer TEXT,
                    PRIMARY KEY (user_id, created_at),
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")
            
        try:
            self.cursor.execute('''
                ALTER TABLE checkins ADD COLUMN question_id INTEGER
                                ''')
        except Exception as e:
            print(f"Erro ao criar tabela de check-ins: {e}")

    def get_user(self, user_id):
        try:
            self.cursor.execute("SELECT xp, level FROM users WHERE user_id = ?", (user_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Erro ao obter usuário: {e}")
            return None 

    def update_user(self, user_id, xp, level):
        try:
            self.cursor.execute('''
                INSERT INTO users (user_id, xp, level) VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET xp = ?, level = ?
            ''', (user_id, xp, level, xp, level))
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao atualizar usuário: {e}")
    
    def close(self):
        self.conn.close()
    
    def get_top_users(self):
        try:
            self.cursor.execute("SELECT user_id, xp, level FROM users ORDER BY xp DESC LIMIT 10")
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Erro ao obter top usuários: {e}")
            return []
    
    def get_user_position(self, xp):
        # Conta quantos usuários têm XP maior que o informado
        self.cursor.execute("SELECT COUNT(*) FROM users WHERE xp > ?", (xp,))
        result = self.cursor.fetchone()
        return result[0] + 1 if result else 1
    
    def level_up(self, user_id):
        data = self.get_user(user_id)
        if data:
            xp, level = data
            level += 1
            self.update_user(user_id, xp, level)
            return level
        return None
    
    def add_xp(self, user_id, amount):
        data = self.get_user(user_id)
        if data:
            xp, level = data
            xp += amount
            self.update_user(user_id, xp, level)
            return xp, level
        else:
            self.update_user(user_id, amount, 1)  # Novo usuário começa no nível 1
            return amount, 1

    def record_checkin(self, user_id, answer, question_id):
        try:
            self.cursor.execute('''
                INSERT INTO checkins (user_id, answer, question_id) VALUES (?, ?, ?)
            ''', (user_id, answer, question_id))
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao registrar check-in: {e}")
    
    def get_checkin_answer(self, user_id, answer):
        try:
            self.cursor.execute('''
                SELECT COUNT(*) FROM checkins 
                WHERE user_id = ? AND answer = ?
            ''', (user_id, answer))
            result = self.cursor.fetchone()
            return result[0] > 0 if result else False
        except Exception as e:
            print(f"Erro ao verificar check-in: {e}")
            return False
    
    def count_checkins(self, answer):
        try:
            self.cursor.execute('''
                SELECT COUNT(*) FROM checkins 
                WHERE answer = ?
            ''', (answer,))
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Erro ao contar check-ins: {e}")
            return 0
        
    def count_checkins_by_question(self, question_id):
        try:
            self.cursor.execute('''
                SELECT COUNT(*) FROM checkins 
                WHERE question_id = ?
            ''', (question_id,))
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Erro ao contar check-ins por questão: {e}")
            return 0
    
    def get_leaderboard_by_question(self, question_id):
        try:
            self.cursor.execute('''
                SELECT user_id, COUNT(*) as checkin_count 
                FROM checkins 
                WHERE question_id = ?
                GROUP BY user_id 
                ORDER BY created_at DESC 
                LIMIT 10
            ''', (question_id,))
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Erro ao obter leaderboard: {e}")
            return []
    
    def delete_user(self, user_id):
        try:
            self.cursor.execute("DELETE FROM checkins WHERE user_id = ?", (user_id,))
            self.cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao deletar usuário: {e}")

db_user = UserDatabaseManager()  # Instância global do gerenciador de banco de dados
