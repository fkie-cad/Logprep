mod generator;

#[tokio::main]
async fn main() {
    generator::generate().await;
}
