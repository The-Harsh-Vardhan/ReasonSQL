-- ================================================================
-- Chinook Database PostgreSQL Schema and Data
-- ================================================================
-- This script creates the Chinook database schema in Supabase/PostgreSQL.
-- Run this in the Supabase SQL Editor to create all tables with sample data.
--
-- Source: https://github.com/lerocha/chinook-database
-- ================================================================

-- Enable UUID extension (if needed)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- SCHEMA DEFINITION
-- ================================================================

-- Artists Table
CREATE TABLE IF NOT EXISTS "Artist" (
    "ArtistId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

-- Albums Table
CREATE TABLE IF NOT EXISTS "Album" (
    "AlbumId" SERIAL PRIMARY KEY,
    "Title" VARCHAR(160) NOT NULL,
    "ArtistId" INTEGER NOT NULL REFERENCES "Artist"("ArtistId")
);

-- Employees Table
CREATE TABLE IF NOT EXISTS "Employee" (
    "EmployeeId" SERIAL PRIMARY KEY,
    "LastName" VARCHAR(20) NOT NULL,
    "FirstName" VARCHAR(20) NOT NULL,
    "Title" VARCHAR(30),
    "ReportsTo" INTEGER REFERENCES "Employee"("EmployeeId"),
    "BirthDate" TIMESTAMP,
    "HireDate" TIMESTAMP,
    "Address" VARCHAR(70),
    "City" VARCHAR(40),
    "State" VARCHAR(40),
    "Country" VARCHAR(40),
    "PostalCode" VARCHAR(10),
    "Phone" VARCHAR(24),
    "Fax" VARCHAR(24),
    "Email" VARCHAR(60)
);

-- Customers Table
CREATE TABLE IF NOT EXISTS "Customer" (
    "CustomerId" SERIAL PRIMARY KEY,
    "FirstName" VARCHAR(40) NOT NULL,
    "LastName" VARCHAR(20) NOT NULL,
    "Company" VARCHAR(80),
    "Address" VARCHAR(70),
    "City" VARCHAR(40),
    "State" VARCHAR(40),
    "Country" VARCHAR(40),
    "PostalCode" VARCHAR(10),
    "Phone" VARCHAR(24),
    "Fax" VARCHAR(24),
    "Email" VARCHAR(60) NOT NULL,
    "SupportRepId" INTEGER REFERENCES "Employee"("EmployeeId")
);

-- Genres Table
CREATE TABLE IF NOT EXISTS "Genre" (
    "GenreId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

-- MediaTypes Table
CREATE TABLE IF NOT EXISTS "MediaType" (
    "MediaTypeId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

-- Tracks Table
CREATE TABLE IF NOT EXISTS "Track" (
    "TrackId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(200) NOT NULL,
    "AlbumId" INTEGER REFERENCES "Album"("AlbumId"),
    "MediaTypeId" INTEGER NOT NULL REFERENCES "MediaType"("MediaTypeId"),
    "GenreId" INTEGER REFERENCES "Genre"("GenreId"),
    "Composer" VARCHAR(220),
    "Milliseconds" INTEGER NOT NULL,
    "Bytes" INTEGER,
    "UnitPrice" NUMERIC(10,2) NOT NULL
);

-- Invoices Table
CREATE TABLE IF NOT EXISTS "Invoice" (
    "InvoiceId" SERIAL PRIMARY KEY,
    "CustomerId" INTEGER NOT NULL REFERENCES "Customer"("CustomerId"),
    "InvoiceDate" TIMESTAMP NOT NULL,
    "BillingAddress" VARCHAR(70),
    "BillingCity" VARCHAR(40),
    "BillingState" VARCHAR(40),
    "BillingCountry" VARCHAR(40),
    "BillingPostalCode" VARCHAR(10),
    "Total" NUMERIC(10,2) NOT NULL
);

-- InvoiceLines Table
CREATE TABLE IF NOT EXISTS "InvoiceLine" (
    "InvoiceLineId" SERIAL PRIMARY KEY,
    "InvoiceId" INTEGER NOT NULL REFERENCES "Invoice"("InvoiceId"),
    "TrackId" INTEGER NOT NULL REFERENCES "Track"("TrackId"),
    "UnitPrice" NUMERIC(10,2) NOT NULL,
    "Quantity" INTEGER NOT NULL
);

-- Playlists Table
CREATE TABLE IF NOT EXISTS "Playlist" (
    "PlaylistId" SERIAL PRIMARY KEY,
    "Name" VARCHAR(120)
);

-- PlaylistTrack Junction Table
CREATE TABLE IF NOT EXISTS "PlaylistTrack" (
    "PlaylistId" INTEGER NOT NULL REFERENCES "Playlist"("PlaylistId"),
    "TrackId" INTEGER NOT NULL REFERENCES "Track"("TrackId"),
    PRIMARY KEY ("PlaylistId", "TrackId")
);

-- ================================================================
-- SAMPLE DATA (Essential for testing)
-- ================================================================

-- Insert sample Artists
INSERT INTO "Artist" ("ArtistId", "Name") VALUES
(1, 'AC/DC'),
(2, 'Accept'),
(3, 'Aerosmith'),
(4, 'Alanis Morissette'),
(5, 'Alice In Chains')
ON CONFLICT DO NOTHING;

-- Insert sample Genres
INSERT INTO "Genre" ("GenreId", "Name") VALUES
(1, 'Rock'),
(2, 'Jazz'),
(3, 'Metal'),
(4, 'Alternative & Punk'),
(5, 'Classical')
ON CONFLICT DO NOTHING;

-- Insert sample MediaTypes
INSERT INTO "MediaType" ("MediaTypeId", "Name") VALUES
(1, 'MPEG audio file'),
(2, 'Protected AAC audio file'),
(3, 'Protected MPEG-4 video file')
ON CONFLICT DO NOTHING;

-- Insert sample Albums
INSERT INTO "Album" ("AlbumId", "Title", "ArtistId") VALUES
(1, 'For Those About To Rock We Salute You', 1),
(2, 'Balls to the Wall', 2),
(3, 'Restless and Wild', 2),
(4, 'Let There Be Rock', 1),
(5, 'Big Ones', 3)
ON CONFLICT DO NOTHING;

-- Note: Full Chinook data can be imported from:
-- https://github.com/lerocha/chinook-database/blob/master/ChinookDatabase/DataSources/Chinook_PostgreSql.sql

-- ================================================================
-- VERIFICATION QUERIES
-- ================================================================

-- Verify tables created
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';

-- Verify sample data
-- SELECT COUNT(*) FROM "Artist";
-- SELECT COUNT(*) FROM "Album";
