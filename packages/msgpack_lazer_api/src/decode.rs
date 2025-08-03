use chrono::{TimeZone, Utc};
use pyo3::types::PyDict;
use pyo3::{prelude::*, IntoPyObjectExt};
use std::io::Read;

pub fn read_object(
    py: Python<'_>,
    cursor: &mut std::io::Cursor<&[u8]>,
    api_mod: bool,
) -> PyResult<PyObject> {
    match rmp::decode::read_marker(cursor) {
        Ok(marker) => match marker {
            rmp::Marker::Null => Ok(py.None()),
            rmp::Marker::True => Ok(true.into_py_any(py)?),
            rmp::Marker::False => Ok(false.into_py_any(py)?),
            rmp::Marker::FixPos(val) => Ok(val.into_pyobject(py)?.into_any().unbind()),
            rmp::Marker::FixNeg(val) => Ok(val.into_pyobject(py)?.into_any().unbind()),
            rmp::Marker::U8 => {
                let mut buf = [0u8; 1];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                Ok(buf[0].into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::U16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = u16::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::U32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = u32::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::U64 => {
                let mut buf = [0u8; 8];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = u64::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::I8 => {
                let mut buf = [0u8; 1];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = i8::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::I16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = i16::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::I32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = i32::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::I64 => {
                let mut buf = [0u8; 8];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = i64::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::Bin8 => {
                let mut buf = [0u8; 1];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = buf[0] as u32;
                let mut data = vec![0u8; len as usize];
                cursor.read_exact(&mut data).map_err(to_py_err)?;
                Ok(data.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::Bin16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u16::from_be_bytes(buf) as u32;
                let mut data = vec![0u8; len as usize];
                cursor.read_exact(&mut data).map_err(to_py_err)?;
                Ok(data.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::Bin32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u32::from_be_bytes(buf);
                let mut data = vec![0u8; len as usize];
                cursor.read_exact(&mut data).map_err(to_py_err)?;
                Ok(data.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::FixStr(len) => read_string(py, cursor, len as u32),
            rmp::Marker::Str8 => {
                let mut buf = [0u8; 1];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = buf[0] as u32;
                read_string(py, cursor, len)
            }
            rmp::Marker::Str16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u16::from_be_bytes(buf) as u32;
                read_string(py, cursor, len)
            }
            rmp::Marker::Str32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u32::from_be_bytes(buf);
                read_string(py, cursor, len)
            }
            rmp::Marker::FixArray(len) => read_array(py, cursor, len as u32, api_mod),
            rmp::Marker::Array16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u16::from_be_bytes(buf) as u32;
                read_array(py, cursor, len, api_mod)
            }
            rmp::Marker::Array32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u32::from_be_bytes(buf);
                read_array(py, cursor, len, api_mod)
            }
            rmp::Marker::FixMap(len) => read_map(py, cursor, len as u32),
            rmp::Marker::Map16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u16::from_be_bytes(buf) as u32;
                read_map(py, cursor, len)
            }
            rmp::Marker::Map32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u32::from_be_bytes(buf);
                read_map(py, cursor, len)
            }
            rmp::Marker::F32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = f32::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::F64 => {
                let mut buf = [0u8; 8];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let val = f64::from_be_bytes(buf);
                Ok(val.into_pyobject(py)?.into_any().unbind())
            }
            rmp::Marker::FixExt1 => read_ext(py, cursor, 1),
            rmp::Marker::FixExt2 => read_ext(py, cursor, 2),
            rmp::Marker::FixExt4 => read_ext(py, cursor, 4),
            rmp::Marker::FixExt8 => read_ext(py, cursor, 8),
            rmp::Marker::FixExt16 => read_ext(py, cursor, 16),
            rmp::Marker::Ext8 => {
                let mut buf = [0u8; 1];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = buf[0] as u32;
                read_ext(py, cursor, len)
            }
            rmp::Marker::Ext16 => {
                let mut buf = [0u8; 2];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u16::from_be_bytes(buf) as u32;
                read_ext(py, cursor, len)
            }
            rmp::Marker::Ext32 => {
                let mut buf = [0u8; 4];
                cursor.read_exact(&mut buf).map_err(to_py_err)?;
                let len = u32::from_be_bytes(buf);
                read_ext(py, cursor, len)
            }
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Unsupported MessagePack marker",
            )),
        },
        Err(e) => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Failed to read marker: {:?}",
            e
        ))),
    }
}

fn read_string(
    py: Python<'_>,
    cursor: &mut std::io::Cursor<&[u8]>,
    len: u32,
) -> PyResult<PyObject> {
    let mut buf = vec![0u8; len as usize];
    cursor.read_exact(&mut buf).map_err(to_py_err)?;
    let s = String::from_utf8(buf)
        .map_err(|_| PyErr::new::<pyo3::exceptions::PyUnicodeDecodeError, _>("Invalid UTF-8"))?;
    Ok(s.into_pyobject(py)?.into_any().unbind())
}

fn read_array(
    py: Python,
    cursor: &mut std::io::Cursor<&[u8]>,
    len: u32,
    api_mod: bool,
) -> PyResult<PyObject> {
    let mut items = Vec::new();
    let array_len = if api_mod { len * 2 } else { len };
    let dict = PyDict::new(py);
    let mut i = 0;
    if len == 2 && !api_mod {
        // 姑且这样判断：列表长度为2，第一个元素为长度为2的字符串，api_mod 模式未启用（不存在嵌套 APIMod）
        let obj1 = read_object(py, cursor, false)?;
        if obj1.extract::<String>(py).map_or(false, |k| k.len() == 2) {
            let obj2 = read_object(py, cursor, true)?;

            let api_mod_dict = PyDict::new(py);
            api_mod_dict.set_item("acronym", obj1)?;
            api_mod_dict.set_item("settings", obj2)?;

            return Ok(api_mod_dict.into_pyobject(py)?.into_any().unbind());
        } else {
            items.push(obj1);
            i += 1;
        }
    }
    while i < array_len {
        if api_mod && i % 2 == 0 {
            let key = read_object(py, cursor, false)?;
            let value = read_object(py, cursor, false)?;
            dict.set_item(key, value)?;
            i += 2;
        } else {
            let item = read_object(py, cursor, api_mod)?;
            items.push(item);
            i += 1;
        }
    }

    if api_mod {
        return Ok(dict.into_pyobject(py)?.into_any().unbind());
    } else {
        Ok(items.into_pyobject(py)?.into_any().unbind())
    }
}

fn read_map(py: Python, cursor: &mut std::io::Cursor<&[u8]>, len: u32) -> PyResult<PyObject> {
    let mut pairs = Vec::new();
    for _ in 0..len {
        let key = read_object(py, cursor, false)?;
        let value = read_object(py, cursor, false)?;
        pairs.push((key, value));
    }

    let dict = PyDict::new(py);
    for (key, value) in pairs {
        dict.set_item(key, value)?;
    }
    return Ok(dict.into_pyobject(py)?.into_any().unbind());
}

fn to_py_err(err: std::io::Error) -> PyErr {
    PyErr::new::<pyo3::exceptions::PyIOError, _>(format!("IO error: {}", err))
}

fn read_ext(py: Python, cursor: &mut std::io::Cursor<&[u8]>, len: u32) -> PyResult<PyObject> {
    // Read the extension type
    let mut type_buf = [0u8; 1];
    cursor.read_exact(&mut type_buf).map_err(to_py_err)?;
    let ext_type = type_buf[0] as i8;

    // Read the extension data
    let mut data = vec![0u8; len as usize];
    cursor.read_exact(&mut data).map_err(to_py_err)?;

    // Handle timestamp extension (type = -1)
    if ext_type == -1 {
        read_timestamp(py, &data)
    } else {
        // For other extension types, return as bytes or handle as needed
        Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
            "Unsupported extension type: {}",
            ext_type
        )))
    }
}

fn read_timestamp(py: Python, data: &[u8]) -> PyResult<PyObject> {
    let (secs, nsec) = match data.len() {
        4 => {
            // timestamp32: 4-byte big endian seconds
            let secs = u32::from_be_bytes([data[0], data[1], data[2], data[3]]) as u64;
            (secs, 0u32)
        }
        8 => {
            // timestamp64: 8-byte packed => upper 34 bits nsec, lower 30 bits secs
            let packed = u64::from_be_bytes([
                data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7],
            ]);
            let nsec = (packed >> 34) as u32;
            let secs = packed & 0x3FFFFFFFF; // lower 34 bits
            (secs, nsec)
        }
        12 => {
            // timestamp96: 12 bytes = 4-byte nsec + 8-byte seconds signed
            let nsec = u32::from_be_bytes([data[0], data[1], data[2], data[3]]);
            let secs = i64::from_be_bytes([
                data[4], data[5], data[6], data[7], data[8], data[9], data[10], data[11],
            ]) as u64;
            (secs, nsec)
        }
        _ => {
            return Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid timestamp data length: {}",
                data.len()
            )));
        }
    };
    let time = Utc.timestamp_opt(secs as i64, nsec).single();
    Ok(time.into_pyobject(py)?.into_any().unbind())
}
