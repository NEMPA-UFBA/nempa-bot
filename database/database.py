import sqlite3

class Db_Manager:
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
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")

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

db = Db_Manager()  # Instância global do gerenciador de banco de dados
