// Auth-типы, соответствующие UserRead backend.
export interface User {
  id: string;
  email: string;
  username: string;
  image_file: string;
  is_active: boolean;
  is_superuser: boolean;
  is_verified: boolean;
}