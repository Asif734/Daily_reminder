fn main() {
    println!("cargo:rerun-if-changed=../.env");
    if std::env::var("DESKTOP_API_BASE_URL").is_err() {
        let contents = std::fs::read_to_string("../.env")
            .expect("apps/desktop/.env is required; copy .env.example and set the backend URL");
        let value = contents
            .lines()
            .find_map(|line| line.strip_prefix("DESKTOP_API_BASE_URL="))
            .map(str::trim)
            .filter(|value| !value.is_empty())
            .expect("DESKTOP_API_BASE_URL must be set in apps/desktop/.env");
        println!("cargo:rustc-env=DESKTOP_API_BASE_URL={value}");
    }
    tauri_build::build()
}
