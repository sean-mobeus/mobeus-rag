-- init-db/02-seed-data.sql
-- Optional seed data for testing the admin dashboard

-- Add some test sessions
INSERT INTO session_memory (uuid, role, message, created_at)
VALUES 
    ('test-user-1', 'user', 'Hello, how does your RAG system work?', NOW() - INTERVAL '1 hour'),
    ('test-user-1', 'assistant', 'Our RAG system works by retrieving relevant documents from a vector database and using them to generate contextualized responses.', NOW() - INTERVAL '59 minutes'),
    ('test-user-1', 'user', 'Can you explain more about the embedding process?', NOW() - INTERVAL '58 minutes'),
    ('test-user-1', 'assistant', 'Sure! We use OpenAI''s embedding models to convert documents and queries into vectors that capture semantic meaning. This allows us to find similar content through vector similarity search.', NOW() - INTERVAL '57 minutes'),
    
    ('test-user-2', 'user', 'What''s the latest update on the Mobeus platform?', NOW() - INTERVAL '2 days'),
    ('test-user-2', 'assistant', 'The latest update includes enhanced RAG capabilities, improved voice interaction, and a new admin dashboard for better system monitoring and configuration.', NOW() - INTERVAL '2 days'),
    
    ('test-user-3', 'user', 'How can I deploy Mobeus in a Docker environment?', NOW() - INTERVAL '3 hours'),
    ('test-user-3', 'assistant', 'You can deploy Mobeus using Docker Compose. The setup includes containers for the backend, frontend, database, and NGINX for routing. Check out the mobeus-devops-guide.md for detailed instructions.', NOW() - INTERVAL '2 hours 55 minutes');

-- Add persistent memory entries
INSERT INTO persistent_memory (uuid, summary, created_at, updated_at)
VALUES 
    ('test-user-1', 'User is interested in technical details of RAG systems, particularly embedding process and vector databases. Shows technical knowledge.', NOW() - INTERVAL '59 minutes', NOW() - INTERVAL '57 minutes'),
    ('test-user-2', 'User inquired about recent platform updates. Appears to be a regular user checking on new features.', NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'),
    ('test-user-3', 'User is interested in Docker deployment. Likely a developer or DevOps engineer looking to set up Mobeus.', NOW() - INTERVAL '2 hours 55 minutes', NOW() - INTERVAL '2 hours 55 minutes');

-- Add function call logs
INSERT INTO function_calls (call_id, function_name, arguments, result, execution_time, success, created_at, session_uuid)
VALUES 
    ('call-1', 'search_knowledge_base', '{"query": "RAG system"}', '{"sources": ["doc1.md", "doc2.md"], "answer": "RAG systems combine retrieval with generation..."}', 0.245, TRUE, NOW() - INTERVAL '59 minutes', 'test-user-1'),
    ('call-2', 'search_knowledge_base', '{"query": "embedding process"}', '{"sources": ["embedding_guide.md"], "answer": "The embedding process converts text to vectors..."}', 0.189, TRUE, NOW() - INTERVAL '57 minutes', 'test-user-1'),
    ('call-3', 'update_user_memory', '{"user_uuid": "test-user-1", "information": "User is interested in RAG technical details"}', '{"success": true}', 0.076, TRUE, NOW() - INTERVAL '57 minutes', 'test-user-1'),
    ('call-4', 'search_knowledge_base', '{"query": "Mobeus updates"}', '{"sources": ["changelog.md"], "answer": "Recent updates include..."}', 0.210, TRUE, NOW() - INTERVAL '2 days', 'test-user-2'),
    ('call-5', 'search_knowledge_base', '{"query": "Docker deployment"}', '{"sources": ["devops_guide.md"], "answer": "Docker deployment instructions..."}', 0.198, TRUE, NOW() - INTERVAL '2 hours 55 minutes', 'test-user-3');

-- Insert more system configuration values
INSERT INTO system_config (key, value, description)
VALUES 
    ('REALTIME_MODEL', 'gpt-4o-realtime-preview-2024-12-17', 'OpenAI Realtime API model for voice interactions'),
    ('REALTIME_VOICE', 'alloy', 'Voice to use for text-to-speech in realtime API'),
    ('RAG_RESULT_COUNT', '5', 'Number of documents to retrieve for each RAG query'),
    ('EMBED_MODEL', 'text-embedding-3-small', 'Model used for document embeddings'),
    ('RAG_TEMPERATURE', '0.2', 'Temperature for RAG completions')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;