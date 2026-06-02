-- =============================================================================
-- Chinook Database Schema (PostgreSQL)
-- For ReasonSQL on Supabase
-- =============================================================================

-- Drop tables if re-running (in reverse FK order)
DROP TABLE IF EXISTS "PlaylistTrack" CASCADE;
DROP TABLE IF EXISTS "InvoiceLine" CASCADE;
DROP TABLE IF EXISTS "Invoice" CASCADE;
DROP TABLE IF EXISTS "Track" CASCADE;
DROP TABLE IF EXISTS "Playlist" CASCADE;
DROP TABLE IF EXISTS "Album" CASCADE;
DROP TABLE IF EXISTS "MediaType" CASCADE;
DROP TABLE IF EXISTS "Genre" CASCADE;
DROP TABLE IF EXISTS "Customer" CASCADE;
DROP TABLE IF EXISTS "Employee" CASCADE;
DROP TABLE IF EXISTS "Artist" CASCADE;

-- Artist
CREATE TABLE "Artist" (
    "ArtistId"  INTEGER NOT NULL,
    "Name"      VARCHAR(120),
    CONSTRAINT "PK_Artist" PRIMARY KEY ("ArtistId")
);

-- Album
CREATE TABLE "Album" (
    "AlbumId"   INTEGER NOT NULL,
    "Title"     VARCHAR(160) NOT NULL,
    "ArtistId"  INTEGER NOT NULL,
    CONSTRAINT "PK_Album" PRIMARY KEY ("AlbumId"),
    CONSTRAINT "FK_AlbumArtistId" FOREIGN KEY ("ArtistId") REFERENCES "Artist" ("ArtistId")
);

-- Employee
CREATE TABLE "Employee" (
    "EmployeeId"    INTEGER NOT NULL,
    "LastName"      VARCHAR(20) NOT NULL,
    "FirstName"     VARCHAR(20) NOT NULL,
    "Title"         VARCHAR(30),
    "ReportsTo"     INTEGER,
    "BirthDate"     TIMESTAMP,
    "HireDate"      TIMESTAMP,
    "Address"       VARCHAR(70),
    "City"          VARCHAR(40),
    "State"         VARCHAR(40),
    "Country"       VARCHAR(40),
    "PostalCode"    VARCHAR(10),
    "Phone"         VARCHAR(24),
    "Fax"           VARCHAR(24),
    "Email"         VARCHAR(60),
    CONSTRAINT "PK_Employee" PRIMARY KEY ("EmployeeId"),
    CONSTRAINT "FK_EmployeeReportsTo" FOREIGN KEY ("ReportsTo") REFERENCES "Employee" ("EmployeeId")
);

-- Genre
CREATE TABLE "Genre" (
    "GenreId"   INTEGER NOT NULL,
    "Name"      VARCHAR(120),
    CONSTRAINT "PK_Genre" PRIMARY KEY ("GenreId")
);

-- Customer
CREATE TABLE "Customer" (
    "CustomerId"    INTEGER NOT NULL,
    "FirstName"     VARCHAR(40) NOT NULL,
    "LastName"      VARCHAR(20) NOT NULL,
    "Company"       VARCHAR(80),
    "Address"       VARCHAR(70),
    "City"          VARCHAR(40),
    "State"         VARCHAR(40),
    "Country"       VARCHAR(40),
    "PostalCode"    VARCHAR(10),
    "Phone"         VARCHAR(24),
    "Fax"           VARCHAR(24),
    "Email"         VARCHAR(60) NOT NULL,
    "SupportRepId"  INTEGER,
    CONSTRAINT "PK_Customer" PRIMARY KEY ("CustomerId"),
    CONSTRAINT "FK_CustomerSupportRepId" FOREIGN KEY ("SupportRepId") REFERENCES "Employee" ("EmployeeId")
);

-- Invoice
CREATE TABLE "Invoice" (
    "InvoiceId"         INTEGER NOT NULL,
    "CustomerId"        INTEGER NOT NULL,
    "InvoiceDate"       TIMESTAMP NOT NULL,
    "BillingAddress"    VARCHAR(70),
    "BillingCity"       VARCHAR(40),
    "BillingState"      VARCHAR(40),
    "BillingCountry"    VARCHAR(40),
    "BillingPostalCode" VARCHAR(10),
    "Total"             NUMERIC(10,2) NOT NULL,
    CONSTRAINT "PK_Invoice" PRIMARY KEY ("InvoiceId"),
    CONSTRAINT "FK_InvoiceCustomerId" FOREIGN KEY ("CustomerId") REFERENCES "Customer" ("CustomerId")
);

-- MediaType
CREATE TABLE "MediaType" (
    "MediaTypeId"   INTEGER NOT NULL,
    "Name"          VARCHAR(120),
    CONSTRAINT "PK_MediaType" PRIMARY KEY ("MediaTypeId")
);

-- Playlist
CREATE TABLE "Playlist" (
    "PlaylistId"    INTEGER NOT NULL,
    "Name"          VARCHAR(120),
    CONSTRAINT "PK_Playlist" PRIMARY KEY ("PlaylistId")
);

-- Track
CREATE TABLE "Track" (
    "TrackId"       INTEGER NOT NULL,
    "Name"          VARCHAR(200) NOT NULL,
    "AlbumId"       INTEGER,
    "MediaTypeId"   INTEGER NOT NULL,
    "GenreId"       INTEGER,
    "Composer"      VARCHAR(220),
    "Milliseconds"  INTEGER NOT NULL,
    "Bytes"         INTEGER,
    "UnitPrice"     NUMERIC(10,2) NOT NULL,
    CONSTRAINT "PK_Track" PRIMARY KEY ("TrackId"),
    CONSTRAINT "FK_TrackAlbumId"     FOREIGN KEY ("AlbumId")     REFERENCES "Album"     ("AlbumId"),
    CONSTRAINT "FK_TrackGenreId"     FOREIGN KEY ("GenreId")     REFERENCES "Genre"     ("GenreId"),
    CONSTRAINT "FK_TrackMediaTypeId" FOREIGN KEY ("MediaTypeId") REFERENCES "MediaType" ("MediaTypeId")
);

-- InvoiceLine
CREATE TABLE "InvoiceLine" (
    "InvoiceLineId" INTEGER NOT NULL,
    "InvoiceId"     INTEGER NOT NULL,
    "TrackId"       INTEGER NOT NULL,
    "UnitPrice"     NUMERIC(10,2) NOT NULL,
    "Quantity"      INTEGER NOT NULL,
    CONSTRAINT "PK_InvoiceLine" PRIMARY KEY ("InvoiceLineId"),
    CONSTRAINT "FK_InvoiceLineInvoiceId" FOREIGN KEY ("InvoiceId") REFERENCES "Invoice" ("InvoiceId"),
    CONSTRAINT "FK_InvoiceLineTrackId"   FOREIGN KEY ("TrackId")   REFERENCES "Track"   ("TrackId")
);

-- PlaylistTrack
CREATE TABLE "PlaylistTrack" (
    "PlaylistId"    INTEGER NOT NULL,
    "TrackId"       INTEGER NOT NULL,
    CONSTRAINT "PK_PlaylistTrack" PRIMARY KEY ("PlaylistId", "TrackId"),
    CONSTRAINT "FK_PlaylistTrackPlaylistId" FOREIGN KEY ("PlaylistId") REFERENCES "Playlist" ("PlaylistId"),
    CONSTRAINT "FK_PlaylistTrackTrackId"    FOREIGN KEY ("TrackId")    REFERENCES "Track"    ("TrackId")
);

-- Indexes for common join patterns
CREATE INDEX "IFK_AlbumArtistId"           ON "Album"         ("ArtistId");
CREATE INDEX "IFK_CustomerSupportRepId"    ON "Customer"      ("SupportRepId");
CREATE INDEX "IFK_EmployeeReportsTo"       ON "Employee"      ("ReportsTo");
CREATE INDEX "IFK_InvoiceCustomerId"       ON "Invoice"       ("CustomerId");
CREATE INDEX "IFK_InvoiceLineInvoiceId"    ON "InvoiceLine"   ("InvoiceId");
CREATE INDEX "IFK_InvoiceLineTrackId"      ON "InvoiceLine"   ("TrackId");
CREATE INDEX "IFK_PlaylistTrackTrackId"    ON "PlaylistTrack" ("TrackId");
CREATE INDEX "IFK_TrackAlbumId"            ON "Track"         ("AlbumId");
CREATE INDEX "IFK_TrackGenreId"            ON "Track"         ("GenreId");
CREATE INDEX "IFK_TrackMediaTypeId"        ON "Track"         ("MediaTypeId");
