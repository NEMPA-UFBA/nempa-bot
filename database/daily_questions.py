import sqlite3


class DailyQuestionDbManager:
    def __init__(self, db_name="daily_questions.db"):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_question (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                question       TEXT      NOT NULL,
                answer         TEXT      NOT NULL,
                target_date    DATE      NOT NULL,
                channel_id     TEXT      NOT NULL DEFAULT '1465446996390314067',              
                scheduled_time TEXT      NOT NULL DEFAULT '08:00',
                published      BOOLEAN   NOT NULL DEFAULT 0,
                limit_reward   INTEGER,
                is_latex       BOOLEAN   NOT NULL DEFAULT 0,
                image_url      TEXT,                
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by     TEXT      DEFAULT 'system',
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by     TEXT      DEFAULT 'system',
                added_by_team_id  TEXT      NOT NULL
            )
        ''')
        self.conn.commit()

    # ------------------------------------------------------------------
    # Leitura
    # ------------------------------------------------------------------

    def get_all(self, limit: int = None, offset: int = 0) -> list:
        self.cursor.execute('''
            SELECT id, question, answer, target_date, scheduled_time, published,
                   limit_reward, is_latex, image_url, channel_id, added_by_team_id
            FROM daily_question
            ORDER BY target_date ASC, scheduled_time ASC, id ASC
            LIMIT ? OFFSET ?
        ''', [limit if limit is not None else -1, offset])
        return self.cursor.fetchall()
    
    def get_all_by_channel(self, channel_id: str, limit: int = None, offset: int = 0) -> list:
        self.cursor.execute('''
            SELECT id, question, answer, target_date, scheduled_time, published,
                   limit_reward, is_latex, image_url, channel_id, added_by_team_id
            FROM daily_question
            WHERE channel_id = ?
            ORDER BY target_date ASC, scheduled_time ASC, id ASC
            LIMIT ? OFFSET ?
        ''', (channel_id, limit if limit is not None else -1, offset))
        return self.cursor.fetchall()
    
    def get_all_by_team(self, team_id: str, limit: int = None, offset: int = 0) -> list:
        self.cursor.execute('''
            SELECT id, question, answer, target_date, scheduled_time, published,
                   limit_reward, is_latex, image_url, channel_id, added_by_team_id
            FROM daily_question
            WHERE added_by_team_id = ?
            ORDER BY target_date ASC, scheduled_time ASC, id ASC
            LIMIT ? OFFSET ?
        ''', (team_id, limit if limit is not None else -1, offset))
        return self.cursor.fetchall()

    def count(self) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM daily_question")
        return self.cursor.fetchone()[0]

    def count_by_channel(self, channel_id: str) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM daily_question WHERE channel_id = ?", (channel_id,))
        return self.cursor.fetchone()[0]
    
    def count_by_team(self, team_id: str) -> int:
        self.cursor.execute("SELECT COUNT(*) FROM daily_question WHERE added_by_team_id = ?", (team_id,))
        return self.cursor.fetchone()[0]

    def get_by_id(self, question_id: int):
        self.cursor.execute('''
            SELECT id, question, answer, target_date, scheduled_time, published,
                   limit_reward, is_latex, image_url,
                   created_by, updated_at, updated_by, channel_id, added_by_team_id
            FROM daily_question WHERE id = ?
        ''', (question_id,))
        return self.cursor.fetchone()

    def get_pending_for_now(self, date_str: str, time_str: str) -> list:
        """Retorna questões não publicadas com target_date == hoje e scheduled_time <= agora."""
        self.cursor.execute('''
            SELECT id, question, answer, limit_reward, scheduled_time, is_latex, image_url, channel_id
            FROM daily_question
            WHERE target_date    = ?
              AND scheduled_time <= ?
              AND published      = 0
            ORDER BY scheduled_time ASC
        ''', (date_str, time_str))
        return self.cursor.fetchall()

    # ------------------------------------------------------------------
    # Escrita
    # ------------------------------------------------------------------

    def add(self, question: str, answer: str, target_date: str,
            scheduled_time: str = "08:00", limit_reward: int = None,
            is_latex: bool = False, image_url: str = None,
            created_by: str = "system", channel_id: str = "1465446996390314067", added_by_team_id: str = None) -> int | bool:
        try:
            self.cursor.execute('''
                INSERT INTO daily_question
                    (question, answer, target_date, scheduled_time,
                     limit_reward, is_latex, image_url, created_by, updated_by, channel_id, added_by_team_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (question, answer, target_date, scheduled_time,
                  limit_reward, int(is_latex), image_url, created_by, created_by, channel_id, added_by_team_id))
            self.conn.commit()
            return self.cursor.lastrowid
        except Exception as e:
            print(f"[DailyQuestionDb] Erro ao inserir: {e}")
            return False

    def update(self, question_id: int, *,
               question: str = None, answer: str = None,
               target_date: str = None, scheduled_time: str = None,
               published: bool = None, is_latex: bool = None,
               image_url: str = None, clear_image: bool = False,
               updated_by: str = "system", channel_id: str = None, added_by_team_id: str = None) -> bool:
        """
        Atualiza campos opcionais. Para limit_reward use set_limit_reward.
        Passe clear_image=True para remover a imagem (setar NULL).
        """
        fields, params = [], []
        if question       is not None: fields.append("question = ?");       params.append(question)
        if answer         is not None: fields.append("answer = ?");         params.append(answer)
        if target_date    is not None: fields.append("target_date = ?");    params.append(target_date)
        if scheduled_time is not None: fields.append("scheduled_time = ?"); params.append(scheduled_time)
        if published      is not None: fields.append("published = ?");      params.append(int(published))
        if is_latex       is not None: fields.append("is_latex = ?");       params.append(int(is_latex))
        if channel_id     is not None: fields.append("channel_id = ?");     params.append(channel_id)
        if added_by_team_id is not None: fields.append("added_by_team_id = ?"); params.append(added_by_team_id)
        if clear_image:
            fields.append("image_url = ?"); params.append(None)
        elif image_url is not None:
            fields.append("image_url = ?"); params.append(image_url)

        if not fields:
            return False

        fields.append("updated_at = CURRENT_TIMESTAMP")
        fields.append("updated_by = ?")
        params.append(updated_by)
        params.append(question_id)

        self.cursor.execute(
            f"UPDATE daily_question SET {', '.join(fields)} WHERE id = ?",
            tuple(params)
        )
        self.conn.commit()
        return self.cursor.rowcount > 0

    def set_limit_reward(self, question_id: int, limit_reward: int | None,
                         updated_by: str = "system") -> bool:
        """Passe None para remover o limite de early bird."""
        try:
            self.cursor.execute(
                '''UPDATE daily_question
                   SET limit_reward = ?, updated_at = CURRENT_TIMESTAMP, updated_by = ?
                   WHERE id = ?''',
                (limit_reward, updated_by, question_id)
            )
            self.conn.commit()
            return self.cursor.rowcount > 0
        except Exception as e:
            print(f"[DailyQuestionDb] Erro ao atualizar limit_reward: {e}")
            return False

    def delete(self, question_id: int) -> bool:
        self.cursor.execute("DELETE FROM daily_question WHERE id = ?", (question_id,))
        self.conn.commit()
        return self.cursor.rowcount > 0


db_daily_question = DailyQuestionDbManager()