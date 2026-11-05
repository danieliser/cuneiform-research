CREATE TABLE registry(version VARCHAR PRIMARY KEY, parser_version VARCHAR NOT NULL);
INSERT INTO registry VALUES ('2', 'conservative-4');
CREATE TABLE source_record(id VARCHAR PRIMARY KEY, namespace VARCHAR NOT NULL, source_key VARCHAR NOT NULL, locator VARCHAR NOT NULL, raw_json JSON NOT NULL);
CREATE TABLE artifact(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), catalog_key VARCHAR NOT NULL, metadata JSON NOT NULL);
CREATE TABLE witness(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), artifact_id VARCHAR NOT NULL REFERENCES artifact(id), scope VARCHAR NOT NULL);
CREATE TABLE composition(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), source_key VARCHAR NOT NULL);
CREATE TABLE passage(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), composition_id VARCHAR REFERENCES composition(id), source_key VARCHAR NOT NULL);
CREATE TABLE sequence_version(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), witness_id VARCHAR NOT NULL REFERENCES witness(id), field VARCHAR NOT NULL, parser_version VARCHAR NOT NULL, evidence_kind VARCHAR NOT NULL);
CREATE TABLE line(id VARCHAR PRIMARY KEY, sequence_id VARCHAR NOT NULL REFERENCES sequence_version(id), ordinal INTEGER NOT NULL, label VARCHAR, surface VARCHAR, column_label VARCHAR, start_byte BIGINT NOT NULL, end_byte BIGINT NOT NULL);
CREATE TABLE occurrence(id VARCHAR PRIMARY KEY, line_id VARCHAR NOT NULL REFERENCES line(id), position INTEGER NOT NULL, raw VARCHAR NOT NULL, reading VARCHAR, kind VARCHAR NOT NULL CHECK(kind IN ('reading','gap','unsupported','derived_sign')), preservation VARCHAR NOT NULL, certainty VARCHAR NOT NULL, restoration_basis VARCHAR NOT NULL, start_byte BIGINT NOT NULL, end_byte BIGINT NOT NULL, UNIQUE(line_id,position));
CREATE TABLE sign_type(id VARCHAR PRIMARY KEY, namespace VARCHAR NOT NULL, revision VARCHAR NOT NULL, label VARCHAR NOT NULL);
CREATE TABLE word_token(id VARCHAR PRIMARY KEY, sequence_id VARCHAR NOT NULL REFERENCES sequence_version(id), source_locator VARCHAR NOT NULL, form VARCHAR, segmentation VARCHAR NOT NULL);
CREATE TABLE lemma(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), namespace VARCHAR NOT NULL, citation_form VARCHAR, language VARCHAR, pos VARCHAR, revision VARCHAR NOT NULL);
CREATE TABLE sense(id VARCHAR PRIMARY KEY, lemma_id VARCHAR NOT NULL REFERENCES lemma(id), guideword VARCHAR, gloss VARCHAR, source_locator VARCHAR NOT NULL);
CREATE TABLE translation_segment(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), sequence_id VARCHAR REFERENCES sequence_version(id), language VARCHAR NOT NULL, text VARCHAR NOT NULL, author VARCHAR, granularity VARCHAR NOT NULL, locator VARCHAR NOT NULL);
CREATE TABLE claim(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), subject_id VARCHAR NOT NULL, predicate VARCHAR NOT NULL, object_key VARCHAR NOT NULL, status VARCHAR NOT NULL, rationale VARCHAR NOT NULL, details JSON NOT NULL);
CREATE TABLE edge(id VARCHAR PRIMARY KEY, source_id VARCHAR NOT NULL, target_id VARCHAR NOT NULL, kind VARCHAR NOT NULL, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), qualification JSON NOT NULL);
CREATE TABLE rejection(id VARCHAR PRIMARY KEY, locator VARCHAR NOT NULL, reason VARCHAR NOT NULL, raw_json JSON NOT NULL);
CREATE TABLE exclusion(id VARCHAR PRIMARY KEY, source_record_id VARCHAR NOT NULL REFERENCES source_record(id), locator VARCHAR NOT NULL, reason VARCHAR NOT NULL);
CREATE VIEW nodes AS
SELECT id,'Artifact' AS kind FROM artifact UNION ALL SELECT id,'Witness' FROM witness UNION ALL SELECT id,'Composition' FROM composition UNION ALL SELECT id,'Passage' FROM passage UNION ALL SELECT id,'SequenceVersion' FROM sequence_version UNION ALL SELECT id,'Line' FROM line UNION ALL SELECT id,'SignOccurrence' FROM occurrence UNION ALL SELECT id,'WordToken' FROM word_token UNION ALL SELECT id,'Lemma' FROM lemma UNION ALL SELECT id,'Sense' FROM sense UNION ALL SELECT id,'TranslationSegment' FROM translation_segment UNION ALL SELECT id,'SourceRecord' FROM source_record UNION ALL SELECT id,'SignType' FROM sign_type UNION ALL SELECT id,'Claim' FROM claim;
CREATE VIEW next_position AS SELECT source_id,target_id FROM edge WHERE kind='NEXT';
CREATE VIEW token_context AS SELECT o.*,l.ordinal,l.label,s.id sequence_id,s.field,s.evidence_kind,s.witness_id,w.artifact_id,s.source_record_id FROM occurrence o JOIN line l ON o.line_id=l.id JOIN sequence_version s ON l.sequence_id=s.id JOIN witness w ON s.witness_id=w.id;

CREATE TABLE source_binding(source_record_id VARCHAR PRIMARY KEY REFERENCES source_record(id), snapshot_id VARCHAR NOT NULL, raw_sha256 VARCHAR NOT NULL);
CREATE TABLE projection_registry(id VARCHAR PRIMARY KEY, revision VARCHAR NOT NULL, config JSON NOT NULL, source_hash VARCHAR NOT NULL, canonical_hash VARCHAR NOT NULL, assets JSON NOT NULL);
CREATE VIEW ordered_position AS
SELECT t.*,r.namespace,b.snapshot_id,b.raw_sha256,r.locator record_locator,
 row_number() OVER (PARTITION BY t.sequence_id ORDER BY t.ordinal,t.position)-1 sequence_position
FROM token_context t JOIN source_record r ON r.id=t.source_record_id JOIN source_binding b ON b.source_record_id=r.id;
CREATE VIEW catalog_alias AS
SELECT c.*,r.namespace,b.snapshot_id FROM claim c JOIN source_record r ON r.id=c.source_record_id
JOIN source_binding b ON b.source_record_id=r.id WHERE predicate='catalog_alias';
CREATE VIEW translation_context AS
SELECT t.*,r.namespace,b.snapshot_id,b.raw_sha256,r.locator record_locator,s.field,s.witness_id,w.artifact_id
FROM translation_segment t JOIN source_record r ON r.id=t.source_record_id JOIN source_binding b ON b.source_record_id=r.id
LEFT JOIN sequence_version s ON s.id=t.sequence_id LEFT JOIN witness w ON w.id=s.witness_id;
-- Portable graph adds provenance/context relationships, never linguistic alignment.
CREATE VIEW portable_edge AS
SELECT * FROM edge
UNION ALL SELECT 'source-edge:'||id,id,source_record_id,'ATTRIBUTED_TO',source_record_id,'{}'::JSON FROM artifact
UNION ALL SELECT 'source-edge:'||id,id,source_record_id,'ATTRIBUTED_TO',source_record_id,'{}'::JSON FROM sequence_version
UNION ALL SELECT 'source-edge:'||id,id,source_record_id,'ATTRIBUTED_TO',source_record_id,'{}'::JSON FROM claim
UNION ALL SELECT 'claim-edge:'||id,id,subject_id,'CLAIM_SUBJECT',source_record_id,'{}'::JSON FROM claim
UNION ALL SELECT 'source-edge:'||id,id,source_record_id,'ATTRIBUTED_TO',source_record_id,'{}'::JSON FROM translation_segment
UNION ALL SELECT 'context-edge:'||id,id,sequence_id,'PLACED_IN_SEQUENCE',source_record_id,'{"alignment":"unresolved; placement only"}'::JSON FROM translation_segment WHERE sequence_id IS NOT NULL;
