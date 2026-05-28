-- Инициализация базы данных для HH AutoApply
-- Этот скрипт выполняется при первом запуске PostgreSQL контейнера
-- Создаёт таблицы согласно схеме из AGENTS.md

-- Включаем расширение для UUID (если ещё не включено)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_pw TEXT NOT NULL,
    hh_login TEXT,
    hh_password TEXT,               -- зашифрованный пароль Fernet
    resume_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Таблица настроек
CREATE TABLE IF NOT EXISTS settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cover_letter TEXT,
    delay_min INT DEFAULT 1,
    delay_max INT DEFAULT 3,
    rate_limit INT DEFAULT 20,
    headless BOOLEAN DEFAULT TRUE,
    UNIQUE(user_id)                 -- один набор настроек на пользователя
);

-- Таблица задач (jobs)
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode TEXT NOT NULL CHECK (mode IN ('auto', 'manual', 'recommendations')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'running', 'done', 'failed')),
    filters JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE
);

-- Таблица откликов (applies)
CREATE TABLE IF NOT EXISTS applies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vacancy_id TEXT NOT NULL,
    vacancy_url TEXT NOT NULL,
    vacancy_title TEXT NOT NULL,
    company TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('sent', 'skipped', 'error')),
    error_msg TEXT,
    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Индексы для ускорения запросов
CREATE INDEX IF NOT EXISTS idx_applies_user_vacancy ON applies(user_id, vacancy_id);
CREATE INDEX IF NOT EXISTS idx_applies_job_id ON applies(job_id);
CREATE INDEX IF NOT EXISTS idx_applies_applied_at ON applies(applied_at);
CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Комментарии к таблицам (опционально)
COMMENT ON TABLE users IS 'Пользователи системы';
COMMENT ON TABLE settings IS 'Настройки пользователя для автоматических откликов';
COMMENT ON TABLE jobs IS 'Задачи на отклик (запущенные пользователем)';
COMMENT ON TABLE applies IS 'История отправленных откликов на вакансии';

-- Логирование успешного выполнения
DO $$
BEGIN
    RAISE NOTICE 'База данных HH AutoApply инициализирована успешно';
END $$;