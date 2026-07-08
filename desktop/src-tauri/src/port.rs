use std::net::{Ipv4Addr, SocketAddrV4, TcpListener};

/// Find a free TCP port on loopback, preferring `preferred`. A zero/reserved
/// preference means "any free port"; we never return 0 to a caller that will
/// bind it as a fixed URL.
pub fn find_free_port(preferred: u16) -> std::io::Result<u16> {
    if preferred > 0 && is_port_free(preferred) {
        return Ok(preferred);
    }
    ephemeral_port()
}

/// True when `port` can be bound on 127.0.0.1 right now.
pub fn is_port_free(port: u16) -> bool {
    TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, port)).is_ok()
}

fn ephemeral_port() -> std::io::Result<u16> {
    let listener = TcpListener::bind(SocketAddrV4::new(Ipv4Addr::LOCALHOST, 0))?;
    Ok(listener.local_addr()?.port())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn ephemeral_when_preferred_is_zero() {
        let p = find_free_port(0).unwrap();
        assert!(p > 0);
    }

    #[test]
    fn returns_preferred_when_free() {
        // Bind an ephemeral port, free it, then confirm it is reported free.
        let free = find_free_port(0).unwrap();
        assert!(is_port_free(free));
        assert_eq!(find_free_port(free).unwrap(), free);
    }

    #[test]
    fn falls_back_when_preferred_taken() {
        let listener = TcpListener::bind((Ipv4Addr::LOCALHOST, 0)).unwrap();
        let taken = listener.local_addr().unwrap().port();
        assert!(!is_port_free(taken));
        let got = find_free_port(taken).unwrap();
        assert_ne!(got, taken);
    }
}
