class Shop {
  final int id;
  final String name, address, phone, description;
  final bool acceptingBookings, canManage;
  Shop.fromJson(Map<String, dynamic> json)
    : id = json['id'],
      name = json['name'],
      address = json['address'],
      phone = json['phone'],
      description = json['description'],
      acceptingBookings = json['accepting_bookings'],
      canManage = json['can_manage'];
}
