"""
classDiagram
class Album{
 *INTEGER AlbumId
   INTEGER ArtistId
   TEXT Title
}
class Artist{
 *INTEGER ArtistId
   TEXT Name
}
class Customer{
 *INTEGER CustomerId
   TEXT Address
   TEXT City
   TEXT Company
   TEXT Country
   TEXT Email
   TEXT Fax
   TEXT FirstName
   TEXT LastName
   TEXT Phone
   TEXT PostalCode
   TEXT State
   INTEGER SupportRepId
}
class Employee{
 *INTEGER EmployeeId
   TEXT Address
   TEXT BirthDate
   TEXT City
   TEXT Country
   TEXT Email
   TEXT Fax
   TEXT FirstName
   TEXT HireDate
   TEXT LastName
   TEXT Phone
   TEXT PostalCode
   REAL ReportsTo
   TEXT State
   TEXT Title
}
class Genre{
 *INTEGER GenreId
   TEXT Name
}
class Invoice{
 *INTEGER InvoiceId
   TEXT BillingAddress
   TEXT BillingCity
   TEXT BillingCountry
   TEXT BillingPostalCode
   TEXT BillingState
   INTEGER CustomerId
   TEXT InvoiceDate
   REAL Total
}
class InvoiceLine{
 *INTEGER InvoiceLineId
   INTEGER InvoiceId
   INTEGER Quantity
   INTEGER TrackId
   REAL UnitPrice
}
class Track{
 *INTEGER TrackId
   INTEGER AlbumId
   INTEGER Bytes
   TEXT Composer
   INTEGER GenreId
   INTEGER MediaTypeId
   INTEGER Milliseconds
   TEXT Name
   REAL UnitPrice
}
class MediaType{
 *INTEGER MediaTypeId
   TEXT Name
}
class Playlist{
 *INTEGER PlaylistId
   TEXT Name
}
class PlaylistTrack{
 INTEGER PlaylistId
   INTEGER TrackId
}
Artist "0..1" -- "0..n" Album
Employee "0..1" -- "0..n" Customer
Customer "0..1" -- "0..n" Invoice
Invoice "0..1" -- "0..n" InvoiceLine
Track "0..1" -- "0..n" InvoiceLine
Album "0..1" -- "0..n" Track
MediaType "0..1" -- "0..n" Track
Genre "0..1" -- "0..n" Track
Playlist "0..1" -- "0..n" PlaylistTrack
Track "0..1" -- "0..n" PlaylistTrack
"""