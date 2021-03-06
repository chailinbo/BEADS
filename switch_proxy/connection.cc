/******************************************************************************
* Author: Samuel Jero <sjero@purdue.edu>
* SDN Switch-Controller Proxy
******************************************************************************/
#include "connection.h"

Connection::Connection(int fsock, int lport, int rport, struct sockaddr_in *raddr)
{
	bh = HalfConn(fsock, lport, &th);
	th = HalfConn(lport, raddr, rport, &bh);
}

bool Connection::start()
{
	return th.start() && bh.start();
}

bool Connection::isRunning() {
	return bh.isRunning() || th.isRunning();
}

void Connection::stop()
{
	bh.stop();
	th.stop();
	return;
}
