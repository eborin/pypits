/*
 * The MIT License (MIT)
 *
 * Copyright (c) 2015 Caian Benedicto <caian@ggaunicamp.com>
 * Copyright (c) 2014 Ian Liu Rodrigues <ian.liu@ggaunicamp.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy 
 * of this software and associated documentation files (the "Software"), to 
 * deal in the Software without restriction, including without limitation the 
 * rights to use, copy, modify, merge, publish, distribute, sublicense, 
 * and/or sell copies of the Software, and to permit persons to whom the 
 * Software is furnished to do so, subject to the following conditions:
 * 
 * The above copyright notice and this permission notice shall be included in 
 * all copies or substantial portions of the Software.
 * 
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL 
 * THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
 * FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS 
 * IN THE SOFTWARE.
 */

#ifndef __SPITZ_CPP_STREAM_HPP__
#define __SPITZ_CPP_STREAM_HPP__

#include <stdint.h>
#include <arpa/inet.h>

#include <vector>
#include <string>
#include <sstream>
#include <iterator>
#include <exception>
#include <algorithm>

namespace spitz {
    
    class ostream 
    {
    private:
        std::vector<uint8_t> pdata;
        
        static uint64_t spitz_htonll(uint64_t x)
        {
            if (htons(1) == 1)
                return x;
            uint32_t lo = (x & 0xFFFFFFFF00000000) >> 32;
            uint32_t hi = x & 0x00000000FFFFFFFF;
            uint64_t nlo = htonl(lo);
            uint64_t nhi = htonl(hi);
            return nhi << 32 | nlo;
        }
        
        template<typename T> void push_back(const T& v)
        {
            size_t s = this->pdata.size();
            this->pdata.resize(s + sizeof(T));
            reinterpret_cast<T*>(this->pdata.data()+s)[0] = v;
        }
        
        template<typename T> uint16_t hton16(const T& v)
        {
            return htons(reinterpret_cast<const uint16_t*>(&v)[0]);
        }
        
        template<typename T> uint32_t hton32(const T& v)
        {
            return htonl(reinterpret_cast<const uint32_t*>(&v)[0]);
        }
        
        template<typename T> uint64_t hton64(const T& v)
        {
            return spitz_htonll(reinterpret_cast<const uint64_t*>(&v)[0]);
        }

    public:
        ostream() : pdata() { }
        
        void write_bool(const bool& v) { push_back((uint8_t)(v ? 1 : 0)); }
        void write_char(const int8_t& v) { push_back(v); }
        void write_byte(const uint8_t& v) { push_back(v); }
        void write_float(const float& v) { push_back(hton32(v)); }
        void write_double(const double& v) { push_back(hton64(v)); }
        void write_short(const int16_t& v) { push_back(hton16(v)); }
        void write_ushort(const uint16_t& v) { push_back(hton16(v)); }
        void write_int(const int32_t& v) { push_back(hton32(v)); }
        void write_uint(const uint32_t& v) { push_back(hton32(v)); }
        void write_longlong(const int64_t& v) { push_back(hton64(v)); }
        void write_ulonglong(const uint64_t& v) { push_back(hton64(v)); }
        void write_string(const std::string& v)
        { 
            const char *p = v.c_str();
            do { write_char(*p); } 
            while (*p++);
        }
        void write_data(const void* pdata, size_t size)
        {
            std::copy(reinterpret_cast<const uint8_t*>(pdata), 
                reinterpret_cast<const uint8_t*>(pdata) + size, 
                std::back_inserter(this->pdata));
        }
        
        ostream& operator<<(const float& v)       { write_float(v); return *this; }
        ostream& operator<<(const double& v)      { write_double(v); return *this; }
        ostream& operator<<(const int8_t& v)      { write_char(v); return *this; }
        ostream& operator<<(const int16_t& v)     { write_short(v); return *this; }
        ostream& operator<<(const int64_t& v)     { write_longlong(v); return *this; }
        ostream& operator<<(const uint8_t& v)     { write_byte(v); return *this; }
        ostream& operator<<(const uint16_t& v)    { write_ushort(v); return *this; }
        ostream& operator<<(const uint64_t& v)    { write_ulonglong(v); return *this; }
        ostream& operator<<(const int& v)         { write_int(v); return *this; }
        ostream& operator<<(const bool& v)        { write_bool(v); return *this; }
        ostream& operator<<(const std::string& v) { write_string(v); return *this; }

        size_t pos() const 
        {
            return this->pdata.size();
        }
        
        const void* data() const
        {
            return this->pdata.data();
        }
    };
    
    class istream 
    {
    private:
        const uint8_t *pdata;
        size_t sz, pos;
        
        static uint64_t spitz_ntohll(uint64_t x)
        {
            if (ntohs(1) == 1)
                return x;
            uint32_t lo = (x & 0xFFFFFFFF00000000) >> 32;
            uint32_t hi = x & 0x00000000FFFFFFFF;
            uint64_t nlo = htonl(lo);
            uint64_t nhi = htonl(hi);
            return nhi << 32 | nlo;
        }
        
        template<typename T> T ntoh16(const T& v)
        {
            uint16_t x = ntohs(reinterpret_cast<const uint16_t*>(&v)[0]);
            return reinterpret_cast<const T*>(&x)[0];
        }
        
        template<typename T> T ntoh32(const T& v)
        {
            uint32_t x = ntohl(reinterpret_cast<const uint32_t*>(&v)[0]);
            return reinterpret_cast<const T*>(&x)[0];
        }
        
        template<typename T> T ntoh64(const T& v)
        {
            uint64_t x = spitz_ntohll(reinterpret_cast<const uint64_t*>(&v)[0]);
            return reinterpret_cast<const T*>(&x)[0];
        }
        
        template<typename T> T get_as()
        {
            ensure_size(sizeof(T));
            T v = reinterpret_cast<const T*>(this->pdata + this->pos)[0];
            this->pos += sizeof(T);
            return v;
        }
        
        void ensure_size(size_t n)
        {
            if (this->sz - this->pos < n)
                throw std::exception();
        }

    public:
        istream() : 
            pdata(reinterpret_cast<const uint8_t*>(0)), 
            sz(0), 
            pos(0) 
        { 
        }
            
        istream(const void *data, const size_t& size) : 
            pdata(reinterpret_cast<const uint8_t*>(data)), 
            sz(size), 
            pos(0) 
        { 
        }
        
        bool read_bool() { uint8_t v = get_as<uint8_t>(); return v ? true : false; }
        int8_t read_char() { return get_as<int8_t>(); }
        uint8_t read_byte() { return get_as<uint8_t>(); }
        float read_float() { return ntoh32(get_as<float>()); }
        double read_double() { return ntoh64(get_as<double>()); }
        int16_t read_short() { return ntoh16(get_as<int16_t>()); }
        uint16_t read_ushort() { return ntoh16(get_as<uint16_t>()); }
        int32_t read_int() { return ntoh32(get_as<int32_t>()); }
        uint32_t read_uint() { return ntoh32(get_as<uint32_t>()); }
        int64_t read_longlong() { return ntoh64(get_as<int64_t>()); }
        uint64_t read_ulonglong() { return ntoh64(get_as<uint64_t>()); }
        std::string read_string()
        { 
            std::stringstream ss;
            char c;
            while((c = read_char()))
                ss << c;
            return ss.str();
        }
        void read_data(void* pdata, size_t size)
        {
            ensure_size(size);
            
            std::copy(this->pdata + this->pos, this->pdata + this->pos + size, 
                reinterpret_cast<uint8_t*>(pdata));
            
            this->pos += size;
        }

        istream& operator>>(float& v)       { v = read_float(); return *this; }
        istream& operator>>(double& v)      { v = read_double(); return *this; }
        istream& operator>>(int8_t& v)      { v = read_char(); return *this; }
        istream& operator>>(int16_t& v)     { v = read_short(); return *this; }
        istream& operator>>(int64_t& v)     { v = read_longlong(); return *this; }
        istream& operator>>(uint8_t& v)     { v = read_byte(); return *this; }
        istream& operator>>(uint16_t& v)    { v = read_ushort(); return *this; }
        istream& operator>>(uint32_t& v)    { v = read_uint(); return *this; }
        istream& operator>>(uint64_t& v)    { v = read_ulonglong(); return *this; }
        istream& operator>>(int& v)         { v = read_int(); return *this; }
        istream& operator>>(bool& v)        { v = read_bool(); return *this; }
        istream& operator>>(std::string& v) { v = read_string(); return *this; }

        size_t size() const 
        {
            return this->sz;
        }
        
        bool has_data() const 
        {
            return this->pos < this->sz;
        }
    };
};

#endif /* __SPITZ_CPP_STREAM_HPP__ */
