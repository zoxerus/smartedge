wget -O se_network.tar https://tinyurl.com/54ntajmw

expected_md5="4b0180a9b94289d097610ce43655d9e8"
calculated_md5=$(md5sum myfile.txt | awk '{print $1}')

if [ "$calculated_md5" = "$expected_md5" ]; then
    echo "All good, MD5 hash matches"
else
    echo "Error: Attention! MD5 hash does NOT match"
fi


