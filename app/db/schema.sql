-- Structured applicant data extracted from documents

CREATE TABLE IF NOT EXISTS applicants (
    applicant_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255),
    emirates_id VARCHAR(50) UNIQUE,
    date_of_birth DATE,
    nationality VARCHAR(100),
    family_size INT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS financial_profile (
    id SERIAL PRIMARY KEY,
    applicant_id INT REFERENCES applicants(applicant_id),
    monthly_income_aed NUMERIC(12,2),
    total_assets_aed NUMERIC(14,2),
    total_liabilities_aed NUMERIC(14,2),
    credit_score INT,
    employment_status VARCHAR(50),
    source_document VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS eligibility_decisions (
    id SERIAL PRIMARY KEY,
    applicant_id INT REFERENCES applicants(applicant_id),
    decision VARCHAR(20),          -- 'Approved' / 'Declined' / 'Needs Review'
    confidence NUMERIC(4,3),
    reasoning TEXT,
    enablement_recommendation TEXT,
    decided_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS validation_flags (
    id SERIAL PRIMARY KEY,
    applicant_id INT REFERENCES applicants(applicant_id),
    flag_type VARCHAR(100),
    description TEXT,
    severity VARCHAR(20),          -- 'low' / 'medium' / 'high'
    created_at TIMESTAMP DEFAULT NOW()
);
