use crate::APIMod;
use chrono::{DateTime, Utc};
use pyo3::prelude::{PyAnyMethods, PyDictMethods, PyListMethods, PyStringMethods};
use pyo3::types::{PyBool, PyBytes, PyDateTime, PyDict, PyFloat, PyInt, PyList, PyNone, PyString};
use pyo3::{Bound, PyAny, PyRef, Python};
use std::io::Write;

fn write_list(buf: &mut Vec<u8>, obj: &Bound<'_, PyList>) {
    rmp::encode::write_array_len(buf, obj.len() as u32).unwrap();
    for item in obj.iter() {
        write_object(buf, &item);
    }
}

fn write_string(buf: &mut Vec<u8>, obj: &Bound<'_, PyString>) {
    let s = obj.to_string_lossy();
    rmp::encode::write_str(buf, &s).unwrap();
}

fn write_integer(buf: &mut Vec<u8>, obj: &Bound<'_, PyInt>) {
    if let Ok(val) = obj.extract::<i32>() {
        rmp::encode::write_i32(buf, val).unwrap();
    } else if let Ok(val) = obj.extract::<i64>() {
        rmp::encode::write_i64(buf, val).unwrap();
    } else {
        panic!("Unsupported integer type");
    }
}

fn write_float(buf: &mut Vec<u8>, obj: &Bound<'_, PyAny>) {
    if let Ok(val) = obj.extract::<f32>() {
        rmp::encode::write_f32(buf, val).unwrap();
    } else if let Ok(val) = obj.extract::<f64>() {
        rmp::encode::write_f64(buf, val).unwrap();
    } else {
        panic!("Unsupported float type");
    }
}

fn write_bool(buf: &mut Vec<u8>, obj: &Bound<'_, PyBool>) {
    if let Ok(b) = obj.extract::<bool>() {
        rmp::encode::write_bool(buf, b).unwrap();
    } else {
        panic!("Unsupported boolean type");
    }
}

fn write_bin(buf: &mut Vec<u8>, obj: &Bound<'_, PyBytes>) {
    if let Ok(bytes) = obj.extract::<Vec<u8>>() {
        rmp::encode::write_bin(buf, &bytes).unwrap();
    } else {
        panic!("Unsupported binary type");
    }
}

fn write_hashmap(buf: &mut Vec<u8>, obj: &Bound<'_, PyDict>) {
    rmp::encode::write_map_len(buf, obj.len() as u32).unwrap();
    for (key, value) in obj.iter() {
        write_object(buf, &key);
        write_object(buf, &value);
    }
}

fn write_nil(buf: &mut Vec<u8>){
    rmp::encode::write_nil(buf).unwrap();
}

// https://github.com/ppy/osu/blob/3dced3/osu.Game/Online/API/ModSettingsDictionaryFormatter.cs
fn write_api_mod(buf: &mut Vec<u8>, api_mod: PyRef<APIMod>) {
    rmp::encode::write_array_len(buf, 2).unwrap();
    rmp::encode::write_str(buf, &api_mod.acronym).unwrap();
    rmp::encode::write_array_len(buf, api_mod.settings.len() as u32).unwrap();
    for (k, v) in api_mod.settings.iter() {
        rmp::encode::write_str(buf, k).unwrap();
        Python::with_gil(|py| write_object(buf, &v.bind(py)));
    }
}

fn write_datetime(buf: &mut Vec<u8>, obj: &Bound<'_, PyDateTime>) {
    if let Ok(dt) = obj.extract::<DateTime<Utc>>() {
        let secs = dt.timestamp();
        let nsec = dt.timestamp_subsec_nanos();
        write_timestamp(buf, secs, nsec);
    } else {
        panic!("Unsupported datetime type. Check your input, timezone is needed.");
    }
}

fn write_timestamp(wr: &mut Vec<u8>, secs: i64, nsec: u32) {
    let buf: Vec<u8> = if nsec == 0 && secs >= 0 && secs <= u32::MAX as i64 {
        // timestamp32: 4-byte big endian seconds
        secs.to_be_bytes()[4..].to_vec()
    } else if secs >= -(1 << 34) && secs < (1 << 34) {
        // timestamp64: 8-byte packed => upper 34 bits nsec, lower 34 bits secs
        let packed = ((nsec as u64) << 34) | (secs as u64 & ((1 << 34) - 1));
        packed.to_be_bytes().to_vec()
    } else {
        // timestamp96: 12 bytes = 4-byte nsec + 8-byte seconds signed
        let mut v = Vec::with_capacity(12);
        v.extend_from_slice(&nsec.to_be_bytes());
        v.extend_from_slice(&secs.to_be_bytes());
        v
    };
    rmp::encode::write_ext_meta(wr, buf.len() as u32, -1).unwrap();
    wr.write_all(&buf).unwrap();
}

pub fn write_object(buf: &mut Vec<u8>, obj: &Bound<'_, PyAny>) {
    if let Ok(list) = obj.downcast::<PyList>() {
        write_list(buf, list);
    } else if let Ok(string) = obj.downcast::<PyString>() {
        write_string(buf, string);
    } else if let Ok(integer) = obj.downcast::<PyInt>() {
        write_integer(buf, integer);
    } else if let Ok(float) = obj.downcast::<PyFloat>() {
        write_float(buf, float);
    } else if let Ok(boolean) = obj.downcast::<PyBool>() {
        write_bool(buf, boolean);
    } else if let Ok(bytes) = obj.downcast::<PyBytes>() {
        write_bin(buf, bytes);
    } else if let Ok(dict) = obj.downcast::<PyDict>() {
        write_hashmap(buf, dict);
    } else if let Ok(_none) = obj.downcast::<PyNone>() {
        write_nil(buf);
    } else if let Ok(datetime) = obj.downcast::<PyDateTime>() {
        write_datetime(buf, datetime);
    } else if let Ok(api_mod) = obj.extract::<PyRef<APIMod>>() {
        write_api_mod(buf, api_mod);
    } else {
        panic!("Unsupported type");
    }
}
