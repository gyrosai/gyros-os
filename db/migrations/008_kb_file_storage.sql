-- Adiciona colunas para armazenamento do arquivo original em kb_docs.
-- O upload extrai texto para RAG mas também salva o binário para download.

ALTER TABLE kb_docs ADD COLUMN IF NOT EXISTS file_data BYTEA;
ALTER TABLE kb_docs ADD COLUMN IF NOT EXISTS file_name TEXT;
ALTER TABLE kb_docs ADD COLUMN IF NOT EXISTS file_size INTEGER;
ALTER TABLE kb_docs ADD COLUMN IF NOT EXISTS mime_type TEXT;
