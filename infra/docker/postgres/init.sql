-- Enables the pgvector extension so embedding columns can be defined
-- once domain models exist. No application tables are created here.
CREATE EXTENSION IF NOT EXISTS vector;
