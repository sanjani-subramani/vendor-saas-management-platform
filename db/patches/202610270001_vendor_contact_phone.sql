-- Add contact_phone to vendors for Twilio click-to-call
ALTER TABLE slmct.vendors ADD COLUMN IF NOT EXISTS contact_phone text;
