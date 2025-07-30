mod decode;
mod encode;

use pyo3::prelude::*;
use std::collections::HashMap;

#[pyclass]
struct APIMod {
    #[pyo3(get, set)]
    acronym: String,
    #[pyo3(get, set)]
    settings: HashMap<String, PyObject>,
}

#[pymethods]
impl APIMod {
    #[new]
    fn new(acronym: String, settings: HashMap<String, PyObject>) -> Self {
        APIMod { acronym, settings }
    }

    fn __repr__(&self) -> String {
        format!(
            "APIMod(acronym='{}', settings={:?})",
            self.acronym, self.settings
        )
    }
}

#[pyfunction]
#[pyo3(name = "encode")]
fn encode_py(obj: &Bound<'_, PyAny>) -> PyResult<Vec<u8>> {
    let mut buf = Vec::new();
    encode::write_object(&mut buf, obj);
    Ok(buf)
}

#[pyfunction]
#[pyo3(name = "decode")]
fn decode_py(py: Python, data: &[u8]) -> PyResult<PyObject> {
    let mut cursor = std::io::Cursor::new(data);
    decode::read_object(py, &mut cursor, false)
}

#[pymodule]
fn msgpack_lazer_api(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_py, m)?)?;
    m.add_function(wrap_pyfunction!(decode_py, m)?)?;
    m.add_class::<APIMod>()?;
    Ok(())
}
