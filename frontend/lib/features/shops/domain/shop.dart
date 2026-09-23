class Shop {
  final int id;
  final String name, address, phone, description;
  final bool acceptingBookings, canManage;
  final String? photo;
  final double? latitude, longitude;
  Shop.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      name = json['name'],
      address = json['address'],
      phone = json['phone'],
      description = json['description'],
      photo = json['photo'] as String?,
      latitude = double.tryParse('${json['latitude']}'),
      longitude = double.tryParse('${json['longitude']}'),
      acceptingBookings = json['accepting_bookings'],
      canManage = json['can_manage'];
}
