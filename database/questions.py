import sqlite3

class QuestionDatabaseManager:
    def __init__(self, db_name="questions.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS question (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    target_date DATE
                )
            ''')
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao criar tabelas: {e}")
            
        try:
            self.cursor.execute('''
                ALTER TABLE question ADD COLUMN limit_secret_reward INTEGER DEFAULT 3
                                ''')
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao criar coluna limit_secret_reward: {e}")
            
        try:
            self.cursor.execute('''
                ALTER TABLE question ADD COLUMN published BOOLEAN DEFAULT 0
                                ''')
            self.conn.commit()
        except Exception as e:
            print(f"Erro ao criar coluna published: {e}")
    
    def get_all_questions(self, limit=None, offset=0, only_published=False):
        try:
            query = '''
                SELECT id, question, answer, target_date FROM question
            '''
            params = []
            if only_published:
                query += " WHERE published = 1"
            query += f" ORDER BY id ASC LIMIT ? OFFSET ?"
            params.extend([limit if limit is not None else -1, offset])
            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except Exception as e:
            print(f"Erro ao obter todas as perguntas: {e}")
            return []
    
    def count_questions(self, only_published=False):
        try:
            query = "SELECT COUNT(*) FROM question"
            if only_published:
                query += " WHERE published = 1"
            self.cursor.execute(query)
            return self.cursor.fetchone()[0]
        except Exception as e:
            print(f"Erro ao contar perguntas: {e}")
            return 0
    
    def get_question_by_id(self, question_id):
        try:
            self.cursor.execute('''
                SELECT id, question, answer, published, target_date FROM question WHERE id = ?
            ''', (question_id,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Erro ao obter pergunta por ID: {e}")
            return None
    
    def get_question_by_answer(self, answer):
        try:
            self.cursor.execute('''
                SELECT id, question, answer, limit_secret_reward, target_date FROM question WHERE answer = ?
            ''', (answer,))
            return self.cursor.fetchone()
        except Exception as e:
            print(f"Erro ao obter pergunta por resposta: {e}")
            return None

    def save_question(self, question, answer, target_date=None, limit_secret_reward=3):
        try:
            exist_question = self.get_question_by_answer(answer)
            if exist_question:
                print(f"Pergunta com resposta '{answer}' já existe. Ignorando inserção.")
                return False
        except Exception as e:
            print(f"Erro ao verificar existência da pergunta: {e}")
            return False
        
        try:
            self.cursor.execute('''
                INSERT INTO question (question, answer, target_date, limit_secret_reward) VALUES (?, ?, ?, ?)
            ''', (question, answer, target_date, limit_secret_reward))
            self.conn.commit()
            return self.cursor.lastrowid  # Retorna o ID da questão inserida
        except Exception as e:
            print(f"Erro ao salvar pergunta: {e}")
            return False
        
    def delete_question_by_id(self, question_id):
        try:
            self.cursor.execute('''
                DELETE FROM question WHERE id = ?
            ''', (question_id,))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao deletar pergunta: {e}")
            return False
    
    def alter_question(self, question_id, new_question=None, new_answer=None, new_target_date=None, published=None):
        try:
            updates = []
            params = []
            if new_question:
                updates.append("question = ?")
                params.append(new_question)
            if new_answer:
                updates.append("answer = ?")
                params.append(new_answer)
            if new_target_date:
                updates.append("target_date = ?")
                params.append(new_target_date)
            if published is not None:
                updates.append("published = ?")
                params.append(published)
            if not updates:
                print("Nenhuma atualização fornecida.")
                return False
            
            params.append(question_id)
            sql = f"UPDATE question SET {', '.join(updates)} WHERE id = ?"
            self.cursor.execute(sql, tuple(params))
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"Erro ao alterar pergunta: {e}")
            return False    


db_question = QuestionDatabaseManager()  # Instância global do gerenciador de banco de dados de perguntas
