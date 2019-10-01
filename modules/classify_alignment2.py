
def contains(sub, pri):
    M, N = len(pri), len(sub)
    i, LAST = 0, M-N+1
    while True:
        try:
            found = pri.index(sub[0], i, LAST) # find first elem in sub
        except ValueError:
            return False
        if pri[found:found+N] == sub:
            return True
        else:
            i = found+1

def main(chr_id, predicted_splices, splices_to_transcripts, transcripts_to_splices, all_splice_pairs_annotations, all_splice_sites_annotations):
    # FSM
    transcript = ''
    if len(predicted_splices) == 0:
         return "NO_SPLICE", transcript       

    if  tuple(predicted_splices) in splices_to_transcripts[chr_id]:
        pred_transcripts = splices_to_transcripts[chr_id][tuple(predicted_splices)]
        if type(pred_transcripts) == str:
            transcript = pred_transcripts
        else:
            transcript = ",".join( tr for tr in splices_to_transcripts[chr_id][tuple(predicted_splices)])  
        print()
        print('Found, FSM:', transcript, predicted_splices)
        print()
        return "FSM", transcript

    # NIC 
    all_splice_sites_annotations_chromosome = all_splice_sites_annotations[chr_id] 
    is_nic = True
    for start, stop in predicted_splices:
        if start not in all_splice_sites_annotations_chromosome or stop not in all_splice_sites_annotations_chromosome:
            is_nic = False
    if is_nic:
        all_splice_pairs_annotations_chromosome = all_splice_pairs_annotations[chr_id]
        is_nic_comb = True
        for start, stop in predicted_splices:
            if (start, stop) not in all_splice_pairs_annotations_chromosome:
                is_nic_comb = False


        if is_nic_comb:
            print()
            print('Found, NIC/ISM (new combination /or incomplete number of exons):', tuple(predicted_splices) )
            print()             
            for ann_tr in splices_to_transcripts[chr_id]:
                print(splices_to_transcripts[chr_id][ann_tr] ,ann_tr)

            return  "ISM/NIC_known", transcript

        else:
            print()
            print('Found, NIC (new donor-acceptor pair):', tuple(predicted_splices) )
            print()   
            return   "NIC_novel", transcript   

    # ISM
    print(all_splice_pairs_annotations[chr_id])
    # print(all_splice_sites_annotations[chr_id])
    hits = [all_splice_pairs_annotations[chr_id][splice_pair] for splice_pair in all_splice_pairs_annotations[chr_id]]
    print(hits)
    print(predicted_splices)
    in_all_pairs = set.intersection(*hits)
    print(in_all_pairs)
    for transcript_id in in_all_pairs:
        transcript_splices = transcripts_to_splices[chr_id][transcript_id]
        print('LOOOOOL', predicted_splices, transcript_splices)
        if contains(predicted_splices, transcript_splices):
            # print("Found, ISM to", transcript_id )
            transcript = transcript_id
            return "ISM", transcript
        else:
            print(predicted_splices, transcript)


       
    print()
    print('NNC:', tuple(predicted_splices) )
    print()       
    return "NNC", transcript
