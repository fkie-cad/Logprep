use log::{info, trace, warn};
use reqwest;
use std::fs::File;
use std::io::{BufRead, BufReader};

pub enum GeneratorError {
    IoError(std::io::Error),
    ReqwestError(reqwest::Error),
}

pub async fn generate() -> Result<(), GeneratorError> {
    let file = match File::open("/tmp/logprep_1o7t74t3/logprep_input_data_0000.txt") {
        Ok(file) => file,
        Err(e) => return Err(GeneratorError::IoError(e)),
    };
    let reader = BufReader::new(file);
    let client = reqwest::Client::new();
    for result in reader.lines() {
        let res = match result {
            Ok(line) => {
                let parts: Vec<&str> = line.splitn(2, ',').collect();
                let path = parts[0];
                let payload = parts[1];
                info!("sending to Path: {} ", path);
                info!("Payload: {}", payload);
                client
                    .post(format!("http://localhost:9000{path}"))
                    .header("Content-Type", "application/json")
                    .body(payload.to_string())
                    .send()
                    .await
            }
            Err(e) => return Err(GeneratorError::IoError(e)),
        };
        let res = match res {
            Ok(res) => res,
            Err(e) => return Err(GeneratorError::ReqwestError(e)),
        };
        info!("Status: {}", res.status());
        info!("Headers:\n{:#?}", res.headers());

        let body = match res.text().await {
            Ok(body) => body,
            Err(e) => return Err(GeneratorError::ReqwestError(e)),
        };
        info!("Body:\n{}", body);
    }
    Ok(())
}
