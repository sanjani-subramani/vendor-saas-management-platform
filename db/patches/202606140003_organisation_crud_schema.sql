-- Organisation metadata used by the admin Organisation CRUD APIs.

ALTER TABLE slmct.organisations
  ADD COLUMN IF NOT EXISTS legal_name text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS website_url text,
  ADD COLUMN IF NOT EXISTS country_code char(2) NOT NULL DEFAULT 'AE',
  ADD COLUMN IF NOT EXISTS currency_code char(3) NOT NULL DEFAULT 'AED',
  ADD COLUMN IF NOT EXISTS is_sister_entity boolean NOT NULL DEFAULT true;

ALTER TABLE slmct.organisations
  DROP CONSTRAINT IF EXISTS organisations_country_code_format;

ALTER TABLE slmct.organisations
  ADD CONSTRAINT organisations_country_code_format CHECK (country_code ~ '^[A-Z]{2}$');

ALTER TABLE slmct.organisations
  DROP CONSTRAINT IF EXISTS organisations_currency_code_format;

ALTER TABLE slmct.organisations
  ADD CONSTRAINT organisations_currency_code_format CHECK (currency_code ~ '^[A-Z]{3}$');

CREATE INDEX IF NOT EXISTS idx_organisations_is_active ON slmct.organisations(is_active);
CREATE INDEX IF NOT EXISTS idx_organisations_is_sister_entity ON slmct.organisations(is_sister_entity);

WITH parent AS (
  SELECT id FROM slmct.organisations WHERE code = 'vendorsphere_group' AND is_active = true LIMIT 1
),
seed(code, name, legal_name, description, country_code, currency_code, is_sister_entity, parent_code) AS (
  VALUES
    ('vendorsphere_group', 'VendorSphere Group', 'VendorSphere Group', 'Parent organisation for VendorSphere entities.', 'AE', 'AED', false, NULL::text),
    ('vendorsphere_operations', 'VendorSphere Operations', 'VendorSphere Operations', 'Operations entity for internal services and execution.', 'AE', 'AED', true, 'vendorsphere_group'),
    ('vendorsphere_it_services', 'VendorSphere IT Services', 'VendorSphere IT Services', 'IT services entity for software, subscriptions, and support.', 'AE', 'AED', true, 'vendorsphere_group'),
    ('vendorsphere_admin_services', 'VendorSphere Admin Services', 'VendorSphere Admin Services', 'Administration entity for business operations.', 'AE', 'AED', true, 'vendorsphere_group')
)
UPDATE slmct.organisations o
SET
  parent_id = CASE
    WHEN s.parent_code IS NULL THEN NULL
    ELSE (SELECT id FROM slmct.organisations p WHERE p.code = s.parent_code AND p.is_active = true LIMIT 1)
  END,
  name = s.name,
  legal_name = s.legal_name,
  description = s.description,
  country_code = s.country_code,
  currency_code = s.currency_code,
  is_sister_entity = s.is_sister_entity,
  is_active = true,
  updated_at = now()
FROM seed s
WHERE o.code = s.code AND o.is_active = true;

WITH parent AS (
  SELECT id FROM slmct.organisations WHERE code = 'vendorsphere_group' AND is_active = true LIMIT 1
),
seed(code, name, legal_name, description, country_code, currency_code, is_sister_entity, parent_code) AS (
  VALUES
    ('vendorsphere_group', 'VendorSphere Group', 'VendorSphere Group', 'Parent organisation for VendorSphere entities.', 'AE', 'AED', false, NULL::text),
    ('vendorsphere_operations', 'VendorSphere Operations', 'VendorSphere Operations', 'Operations entity for internal services and execution.', 'AE', 'AED', true, 'vendorsphere_group'),
    ('vendorsphere_it_services', 'VendorSphere IT Services', 'VendorSphere IT Services', 'IT services entity for software, subscriptions, and support.', 'AE', 'AED', true, 'vendorsphere_group'),
    ('vendorsphere_admin_services', 'VendorSphere Admin Services', 'VendorSphere Admin Services', 'Administration entity for business operations.', 'AE', 'AED', true, 'vendorsphere_group')
)
INSERT INTO slmct.organisations (
  parent_id, code, name, legal_name, description, country_code, currency_code, is_sister_entity
)
SELECT
  CASE
    WHEN s.parent_code IS NULL THEN NULL
    ELSE (SELECT id FROM parent)
  END,
  s.code,
  s.name,
  s.legal_name,
  s.description,
  s.country_code,
  s.currency_code,
  s.is_sister_entity
FROM seed s
WHERE NOT EXISTS (
  SELECT 1 FROM slmct.organisations o WHERE o.code = s.code AND o.is_active = true
);
