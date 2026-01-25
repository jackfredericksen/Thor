#!/usr/bin/env python3
"""
Convert Solana keypair array to base58 private key
"""
import base58

# Your keypair array from .env
keypair_array = [133,153,166,204,109,77,88,14,209,14,137,118,87,127,94,246,154,178,178,117,89,82,202,205,147,167,174,178,46,40,185,59,198,249,132,141,18,158,120,45,153,248,22,100,227,226,49,184,199,44,25,3,128,204,140,175,185,140,224,248,86,186,146,115]

# Convert to bytes
keypair_bytes = bytes(keypair_array)

# Encode to base58
base58_key = base58.b58encode(keypair_bytes).decode('utf-8')

print("\n" + "="*60)
print("SOLANA PRIVATE KEY CONVERSION")
print("="*60)
print("\nYour base58 encoded private key:")
print(f"\n{base58_key}\n")
print("="*60)
print("\nUpdate your .env file:")
print(f'THOR_WALLET_PRIVATE_KEY={base58_key}')
print("="*60 + "\n")
