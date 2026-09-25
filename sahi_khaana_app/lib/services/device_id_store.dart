import 'package:uuid/uuid.dart';

/// Where the anonymous device id lives. The backend has no login: this UUID is the ONLY key
/// to a user's scan history, so it must be created once and then reused forever.
/// (Reinstalling the app creates a new id and loses access to the old history.)
abstract interface class DeviceIdStore {
  /// The stored id, creating and storing a new UUID v4 on the very first call.
  Future<String> getOrCreate();
}

/// A UUID (any version), as the backend requires.
final RegExp uuidPattern = RegExp(
  r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$',
);

/// Keeps the id in memory only. For tests and command-line tools, not for the app.
class InMemoryDeviceIdStore implements DeviceIdStore {
  InMemoryDeviceIdStore([this._id]);

  String? _id;

  @override
  Future<String> getOrCreate() async => _id ??= const Uuid().v4();
}
