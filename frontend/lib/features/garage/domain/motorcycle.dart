class Motorcycle {
  final int id, year, mileage;
  final String brand, model, plate, notes;
  const Motorcycle({
    required this.id,
    required this.brand,
    required this.model,
    required this.plate,
    required this.year,
    required this.mileage,
    this.notes = '',
  });
  factory Motorcycle.fromJson(Map<String, dynamic> json) => Motorcycle(
    id: json['id'],
    brand: json['brand'],
    model: json['model'],
    plate: json['license_plate'],
    year: json['year'],
    mileage: json['mileage'],
    notes: json['notes'],
  );
}
