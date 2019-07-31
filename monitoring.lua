--[[
    monitor.lua - InfluxDB driver for YAMAHA RTX series
]]

-- Interface monitoring interval (1-864000 sec)
avr_sec = 1

-- InfluxDB Endpoint
influxdb = "http://192.168.100.2:8086/write?db=rtx1200-lua"

-- Post monitoring value to InfluxDB
function post_influxdb(measurement, field, value)
    local request_tbl = {
        url = influxdb,
        method = "POST",
        content_type = "application/json",
        post_text = string.format("%s %s=%s",measurement,field,value)
    }
    response_tbl = rt.httprequest(request_tbl)
    --print(request_tbl.post_text)
    --print(response_tbl.body)
end

-- Get environment statuses
function get_env_status(tbl)
    local rtn, str
    rtn, str = rt.command("show environment")

    if (rtn) and (str) then
        for k, v in pairs(tbl) do
            v.val = str:match(v.ptn)
            if (v.val) then
                v.val = tostring(v.val)
            end
        end
    else
        return nil, nil
    end

    return rtn, str
end

-- Get DHCP lease status
function get_dhcp_status()
    local rtn, str, i
    local l = {}
    local u = {}

    rtn, str = rt.command("show status dhcp")
    if (rtn) and (str) then
        i = 1
        for w in string.gmatch(str, "Leased%:%s+(%d+)") do
            l[i] = w
            i = i + 1
        end
        i = 1
        for w in string.gmatch(str, "Usable%:%s+(%d+)") do
            u[i] = w
            i = i + 1
        end
    end

    return l, u
end

-- Get NAT status
function get_nat_status()
    local rtn, str, num, ip

    rtn, str = rt.command("show nat descriptor address ")
    if (rtn) and (str) then
        --ip = str:match("ipcp/(%a+)")
        num = str:match("(%d+)%s+used.")
    end

    --if (not ip) then
    --  ip = "0.0.0.0"
    --end
    if (not num) then
        num = "-1"
    end

    --return ip, num
    return num
end

-- Get LAN interface speed
function lan_interface_speed(num)
    local rtn, str, val, rt_name
    local cmd = "show config"
    local ptn = "speed lan" .. tostring(num) .. " (%d+%a)"

    rtn, str = rt.command(cmd)
    if (rtn) and (str) then
        str = str:match(ptn)
        if (str) then
            val = unitstr2num(str)
        end
    end

    if (not val) or (val == 0) then
        val = unitstr2num("1000m")
    end

    return val
end

-- Convert bit string to decimal
function unitstr2num(str)
    local val, unit

    val = tonumber(str:match("%d+"))
    unit = str:sub(-1):lower()

    if (unit == "k") then
        val = val * 1000
    elseif (unit == "m") then
        val = val * 1000 * 1000
    else
        val = 0
    end

    return val
end

-- Get LAN interfaces
function lan_interfaces()
    local rtn, str, n
    local cmd = "show config"
    local ptn = "ip lan(.+) address"
    local t = {}

    rtn, str = rt.command(cmd)

    if (rtn) and (str) then
        n = 1
        for w in string.gmatch(str, ptn) do
            t[n] = w
            n = n + 1
        end
    end

    return t
end

-- Get PP interfaces
function pp_interfaces()
    local rtn, str, n
    local cmd = "show config"
    local ptn = "pp select (%d+)"
    local t = {}

    rtn, str = rt.command(cmd)

    if (rtn) and (str) then
        n = 1
        for w in string.gmatch(str, ptn) do
            t[n] = w
            n = n + 1
        end
    end

    return t
end

-- Get LAN load
function lan_load_info(num, sec)
    local rtn, str1, str2, rcv, snd, rcv_load, snd_load
    local t = {}
    local cmd = "show status lan" .. tostring(num)
    local ptn = "%((%d+)%s+octets?%)"

    rtn, str1 = rt.command(cmd)
    if (rtn) and (str1) then
        rt.sleep(sec)

        rtn, str2 = rt.command(cmd)
        if (rtn) and (str2) then
            str1 = str1 .. str2

            n = 1
            for w in string.gmatch(str1, ptn) do
                t[n] = w
                n = n + 1
            end

            if (t[1]) and (t[3]) then
                snd = (tonumber(t[3]) - tonumber(t[1])) / sec
            end
            if (t[2]) and (t[4]) then
                rcv = (tonumber(t[4]) - tonumber(t[2])) / sec
            end
        end
    end

    return rcv, snd
end

-- Get PP load
function pp_load_info(num, sec)
    local rtn, str1, str2, rcv, rcv_load, snd, snd_load, n
    local t = {}
    local cmd = "show status pp " .. tostring(num)
    local ptn1 = "Load%:%s+(%d+)%.%d+%%"
    local ptn2 = "%[(%d+) octets?%]"

    rtn, str1 = rt.command(cmd)
    if (rtn) and (str1) then
        n = 1
        for w in string.gmatch(str1, ptn1) do
            t[n] = w
            n = n + 1
        end
        if (t[1]) then
            rcv_load = tonumber(t[1])
        end
        if (t[2]) then
            snd_load = tonumber(t[2])
        end
    end

    if (rtn) and (str1) then
        rt.sleep(sec)

        rtn, str2 = rt.command(cmd)
        if (rtn) and (str2) then
            str1 = str1 .. str2

            n = 1
            for w in string.gmatch(str1, ptn2) do
                t[n] = w
                n = n + 1
            end

            if (t[1]) and (t[3]) then
                rcv = ((tonumber(t[3]) - tonumber(t[1])) * 8) / sec
            else
                rtn = false
            end
            if (t[2]) and (t[4]) then
                snd = ((tonumber(t[4]) - tonumber(t[2])) * 8) / sec
            else
                rtn = false
            end
        end
    end

    return rcv, rcv_load, snd, snd_load
end

-- environment pattern
local env_tbl = {
    cpu_5sec = {
        ptn = "(%d+)%%%(5sec%)",
        val = 0
    },
    cpu_1min = {
        ptn = "(%d+)%%%(1min%)",
        val = 0
    },
    cpu_5min = {
        ptn = "(%d+)%%%(5min%)",
        val = 0
    },
    mem = {
        ptn = "(%d+)%% used",
        val = 0
    },
    buf_small = {
        ptn = "(%d+)%%%(small%)",
        val = 0
    },
    buf_middle = {
        ptn = "(%d+)%%%(middle%)",
        val = 0
    },
    buf_large = {
        ptn = "(%d+)%%%(large%)",
        val = 0
    },
    buf_huge = {
        ptn = "(%d+)%%%(huge%)",
        val = 0
    },
    temp = {
        ptn = "Inside Temperature%(C.%): (%d+)",
        val = 0
    },
    uptime = {
        ptn = "Elapsed time from boot: (%d+)days",
        val = 0
    }
}

-- Main loop
function main()
    local i, str, rcv, rcv_load, snd, snd_load
    local l = {}
    local u = {}

    -- Post environment data
    get_env_status(env_tbl)
    post_influxdb("cpu", "5sec", env_tbl.cpu_5sec.val)
    post_influxdb("cpu", "1min", env_tbl.cpu_1min.val)
    post_influxdb("cpu", "5min", env_tbl.cpu_5min.val)
    post_influxdb("memory", "now", env_tbl.mem.val)
    post_influxdb("packet_buffer", "small", env_tbl.buf_small.val)
    post_influxdb("packet_buffer", "middle", env_tbl.buf_middle.val)
    post_influxdb("packet_buffer", "large", env_tbl.buf_large.val)
    post_influxdb("packet_buffer", "huge", env_tbl.buf_huge.val)
    post_influxdb("temperature", "now", env_tbl.temp.val)
    post_influxdb("uptime", "day", env_tbl.uptime.val)

    -- Post DHCP leased data
    l, u = get_dhcp_status()
    for i,v in ipairs(l) do
        post_influxdb("dhcp"..tostring(i), "leased", v)
    end

    -- Post DHCP usable data
    for i,v in ipairs(u) do
        post_influxdb("dhcp"..tostring(i), "usable", v)
    end

    -- Post NAT status
    post_influxdb("nat", "entry", get_nat_status())

    -- Post PP load
    for i in ipairs(pp_interfaces()) do
        rcv, rcv_load, snd, snd_load = pp_load_info(i, avr_sec)
        post_influxdb("pp"..tostring(i) ,"receive",rcv_per)
        post_influxdb("pp"..tostring(i),"transmit",snd_per)
        post_influxdb("pp"..tostring(i),"receive_byte",rcv)
        post_influxdb("pp"..tostring(i),"transmit_byte",snd)
    end

    -- Post LAN load
    for i in ipairs(lan_interfaces()) do
        rcv, snd, imax = lan_load_info(i, avr_sec)
        post_influxdb("lan"..tostring(i), "receive_byte",rcv)
        post_influxdb("lan"..tostring(i), "transmit_byte",snd)
        post_influxdb("lan"..tostring(i), "interface_speed",lan_interface_speed(i))
    end
end

main()
os.exit(0)